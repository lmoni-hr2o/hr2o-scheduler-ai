from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from utils.datastore_helper import get_db
import numpy as np
from typing import List, Optional, Dict, Any
from scorer.model import NeuralScorer
from models import Activity, Employment, AlgorithmConfig
from solver.logger import save_log, get_all_logs
from utils.security import verify_hmac
import json
from google.cloud import datastore
from utils.mapping_helper import mapper
from datetime import datetime
from utils.status_manager import update_status, get_status, set_running
from utils.demand_profiler import DemandProfiler

router = APIRouter(prefix="/training", tags=["Training"])

@router.get("/config", response_model=AlgorithmConfig)
def get_config(environment: str = Depends(verify_hmac)):
    """Retrieves the algorithm configuration for the current environment."""
    client = get_db()
    key = client.key("AlgorithmConfig", environment)
    entity = client.get(key)
    
    if entity:
        return AlgorithmConfig(**entity)
    
    # Return default if not found
    return AlgorithmConfig(environment=environment)

@router.post("/config")
def save_config(config: AlgorithmConfig, environment: str = Depends(verify_hmac)):
    """Saves the algorithm configuration."""
    client = get_db()
    key = client.key("AlgorithmConfig", environment)
    
    entity = datastore.Entity(key=key)
    config_dict = config.dict()
    config_dict["last_updated"] = datetime.now()
    entity.update(config_dict)
    
    client.put(entity)
    return {"status": "success", "message": "Configuration saved"}

class FeedbackRequest(BaseModel):
    action: str
    selected_id: str
    rejected_id: Optional[str] = None
    shift_data: Optional[dict] = {}

class RetrainRequest(BaseModel):
    company_id: Optional[str] = None

@router.get("/progress")
def get_progress(environment: str = Depends(verify_hmac)):
    """Returns the current training progress."""
    return get_status()

@router.get("/model-stats")
def get_model_stats(environment: str = Depends(verify_hmac)):
    """Exposes internal AI metrics for the Developer Hub."""
    scorer = NeuralScorer()
    return scorer.get_stats()

@router.get("/debug-mapper")
def debug_mapper():
    """Returns the internal state of the EnvironmentMapper without HMAC check."""
    from utils.mapping_helper import mapper
    # Add entity counts for debugging
    entities_summary = {}
    for company_name, lists in getattr(mapper, '_entities', {}).items():
        entities_summary[company_name] = {
            "Employment": len(lists.get("Employment", [])),
            "Activity": len(lists.get("Activity", []))
        }
    
    return {
        "mappings": mapper._mappings,
        "entities_summary": entities_summary,
        "id_to_ns": getattr(mapper, '_id_to_ns', {}),
        "last_refresh": mapper._last_refresh
    }

def discover_unique_environments():
    """Returns all discovered companies from the cache with stats."""
    all_mapped = mapper.get_all_companies()
    results = []
    for c in all_mapped:
        cid = c["id"]
        lists = mapper._entities.get(cid, {})
        ac = len(lists.get("Activity", []))
        em = len(lists.get("Employment", []))
        pe = len(lists.get("Period", []))
        
        results.append({
            "id": cid,
            "name": c["name"],
            "namespace": mapper.get_namespace(cid),
            "stats": {"activities": ac, "employees": em, "periods": pe},
            "is_active": (ac > 0 and pe > 0) # User requirement: Activity AND Period
        })
    return results

@router.get("/environments")
def get_environments():
    """Returns a list of all discovered companies (ID and Name) with metadata."""
    envs = discover_unique_environments()
    return {"environments": envs, "count": len(envs)}

@router.post("/log-feedback")
def log_feedback(req: FeedbackRequest, environment: str = Depends(verify_hmac)):
    """
    Logs user corrections to Google Cloud Datastore.
    """
    save_log(req.action, req.selected_id, req.rejected_id, req.shift_data, environment)
    return {"status": "success", "message": f"Feedback stored in Datastore for {environment}"}

@router.on_event("startup")
def startup_event():
    """Initializes the EnvironmentMapper and triggers an initial Global Training in background."""
    import threading
    print("Pre-warming EnvironmentMapper and triggering Initial Learning in background...")
    
    # Safety: Clear any stale "running" locks from previous crashed instances
    set_running(False)
    
    def background_startup():
        try:
            # 1. Discover environments
            mapper.discover_all()
            # 2. Trigger initial training
            print("INFO: Starting automatic startup training...")
            run_global_training()
        except Exception as e:
            print(f"ERROR: Background startup task failed: {e}")

    threading.Thread(target=background_startup, daemon=True).start()

def run_global_training():
    """
    Background Task: Discovers environments from logs, aggregates data, and trains the Global Model.
    """
    set_running(True)
    update_status(message="Starting Global AI Pipeline", progress=0.05, phase="MAPPING", log="Initializing Environment Ingestion Engine...")
    
    try:
        # Warm up the mapper
        update_status("Mapping namespaces and companies...", 0.1, log="Scanning Datastore namespaces [OVERCLEAN, OVERFLOW]...")
        mapper.refresh_if_needed(force=True)
        
        # 1. Discover environments from LearningLog entities
        update_status(log="Discovering environments from logs...")
        
        all_logs_entities = []
        for ns in [None, "OVERCLEAN", "OVERFLOW"]:
            client = get_db(namespace=ns).client
            for kind in ['LearningLog', 'learning_log']:
                try:
                    results = list(client.query(kind=kind).fetch())
                    if results:
                        all_logs_entities.extend(results)
                except: pass
        
        if not all_logs_entities:
            print("INFO: No LearningLog entries found. Proceeding with historical training only.")
            logs_by_primary_env = {}
        else:
            # Group logs by PRIMARY environment ID using the mapper
            logs_by_primary_env = {}
            for entity in all_logs_entities:
                env_val = str(entity.get('environment'))
                if not env_val: continue
                
                # Resolve to primary ID
                primary_id = env_val
                target_info = mapper._mappings.get(env_val) or next((v for v in mapper._mappings.values() if env_val in v.get("aliases", [])), None)
                if target_info:
                    # Find the primary key in mapper entries
                    for k, v in mapper._mappings.items():
                        if v == target_info:
                            primary_id = k
                            break
                
                if primary_id not in logs_by_primary_env:
                    logs_by_primary_env[primary_id] = []
                
                log_dict = dict(entity)
                if 'shift_data' in log_dict and isinstance(log_dict['shift_data'], str):
                    try: log_dict['shift_data'] = json.loads(log_dict['shift_data'])
                    except: pass
                logs_by_primary_env[primary_id].append(log_dict)

        # 1. Discover Environments from Mapper
        companies = mapper.get_all_companies()
        company_ids = [c["id"] for c in companies]
        total_p_envs = len(company_ids)
        
        # 1. Global Role Discovery (CRITICAL for consistent indexing)
        update_status(log="Indexing global roles for feature consistency...")
        all_roles_set = set()
        for primary_id in company_ids:
            try:
                raw_employees = mapper.get_employment(primary_id)
                raw_activities = mapper.get_activities(primary_id)
                for e in raw_employees:
                    all_roles_set.add(str((e.get("employment") or e).get("role", "worker")).strip().upper())
                for a in raw_activities:
                    all_roles_set.add(str((a.get("activities") or a).get("name", "Unknown")).strip().upper())
            except: continue
        
        global_all_roles = sorted(list(all_roles_set))
        print(f"DEBUG: Discovered {len(global_all_roles)} global roles: {global_all_roles}")

        # 2. Iterate and Aggregate using cached metadata
        from utils.date_utils import parse_date, format_date_iso
        scorer = NeuralScorer()
        scorer.load_weights()
        
        all_X = []
        all_y = []
        processed_count = 0
        total_samples = 0
        
        for i, primary_id in enumerate(company_ids):
            update_status(
                message=f"Processing {primary_id}",
                progress=0.15 + (i / total_p_envs) * 0.6,
                phase="EXTRACTION",
                log=f"Extracting features from company: {primary_id}...",
                details={
                    "envs_processed": i + 1,
                    "processed_samples": len(all_X)
                }
            )
            
            try:
                # 0. Fetch Data Mappings for this environment
                client = get_db()
                k = client.key("DataMapping", primary_id)
                mapping_entity = client.get(k)
                env_mappings = mapping_entity.get("mappings") if mapping_entity else None
                
                # Use CACHED metadata from mapper (instant)
                raw_employees = mapper.get_employment(primary_id)
                raw_activities = mapper.get_activities(primary_id)
                raw_periods = mapper.get_periods(primary_id)
                
                # NEW: Learn Demand Profile (Times and Quantities)
                profiler = DemandProfiler(primary_id)
                profiler.learn_from_periods(raw_periods)
                profiler.save_to_datastore()
                
                # Get manual logs if any (using company_id or aliases)
                logs = logs_by_primary_env.get(primary_id, [])
                info = mapper._mappings.get(primary_id, {})
                for alias in info.get("aliases", []):
                    if alias in logs_by_primary_env:
                        logs.extend(logs_by_primary_env[alias])
                
                # Convert raw dicts to Activity/Employment objects
                employees_list = []
                for e in raw_employees:
                    emp_data = (e.get("employment") or e)
                    person = (emp_data.get("person") or {})
                    # Use _entity_id as primary identifier
                    emp_id = str(e.get("_entity_id", "")) or str(emp_data.get("id", "")) or str(e.get("id", ""))
                    employees_list.append(Employment(
                        id=emp_id,
                        name=(emp_data.get("company") or {}).get("name", primary_id),
                        fullName=person.get("fullName", "Unknown"),
                        role=str(emp_data.get("role", "worker")).strip().upper(),
                        environment=primary_id,
                        person=person
                    ))

                emp_map = {e.id: e.dict() for e in employees_list}
                
                # NEW: Build project/client history for each employee for Project Affinity
                for e_id in emp_map:
                    emp_map[e_id]["project_ids"] = set()
                    emp_map[e_id]["customer_keywords"] = set()
                
                for p_data in raw_periods:
                    emp_sub_data = p_data.get("employment", {})
                    # CORRECTION: Do NOT use _entity_id (which is the Period ID) as the Employee ID
                    e_id = str(emp_sub_data.get("id", "")) or str(p_data.get("employmentId", ""))
                    if e_id in emp_map:
                        act = p_data.get("activities", {})
                        p_proj = act.get("project", {})
                        if p_proj:
                            p_id = str(p_proj.get("id") or "")
                            if p_id: emp_map[e_id]["project_ids"].add(p_id)
                            # Extract keywords from customer address/name
                            cust = p_proj.get("customer", {})
                            for k in ["name", "address"]:
                                val = cust.get(k, "")
                                if val: emp_map[e_id]["customer_keywords"].add(str(val).upper()[:5])

                for e_id in emp_map:
                    emp_map[e_id]["project_ids"] = list(emp_map[e_id]["project_ids"])
                    emp_map[e_id]["customer_keywords"] = list(emp_map[e_id]["customer_keywords"])

                # A. Train from LearningLog (manual feedback)
                for log in logs:
                    try:
                        shift = log.get("shift_data", {})
                        if not shift: continue
                        
                        punctuality = 0.95
                        
                        # Positive Sample
                        sel_id = str(log.get("selected_id", ""))
                        if sel_id in emp_map:
                            emp = emp_map[sel_id]
                            emp["punctuality_score"] = punctuality
                            all_X.append(scorer.extract_features(emp, shift, global_all_roles, mappings=env_mappings))
                            all_y.append(1.0)
                        
                        # Negative Sample
                        rej_id = str(log.get("rejected_id", ""))
                        if rej_id and rej_id in emp_map:
                            emp = emp_map[rej_id]
                            emp["punctuality_score"] = punctuality
                            all_X.append(scorer.extract_features(emp, shift, global_all_roles, mappings=env_mappings))
                            all_y.append(0.0)
                            
                            # Class Balancing: Duplicate manual negatives as they are very valuable
                            all_X.append(scorer.extract_features(emp, shift, global_all_roles, mappings=env_mappings))
                            all_y.append(0.0)
                    except: continue
                
                # B. Train from Period (historical assignments)
                # Diagnostic counters
                msgs_dropped_id = 0
                msgs_total = len(raw_periods)
                
                for period_data in raw_periods:
                    try:
                        act_sub_data = period_data.get("activities", {})
                        
                        tmentry = period_data.get("tmentry")
                        tmexit = period_data.get("tmexit")
                        tmregister = period_data.get("tmregister")
                        
                        reg_dt = parse_date(tmregister)
                        if not reg_dt: continue

                        entry_dt = parse_date(tmentry)
                        exit_dt = parse_date(tmexit)
                        
                        shift = {
                            "date": format_date_iso(reg_dt),
                            "start_time": entry_dt.strftime("%H:%M") if entry_dt else "08:00",
                            "end_time": exit_dt.strftime("%H:%M") if exit_dt else "17:00",
                            "role": str(act_sub_data.get("name", "worker")).strip().upper(),
                            "project": act_sub_data.get("project"),
                            "customer_address": (act_sub_data.get("project") or {}).get("customer", {}).get("address") if isinstance(act_sub_data, dict) else None
                        }
                        
                        # CORRECTION: Do NOT use _entity_id (which is the Period ID) as the Employee ID
                        emp_id = str(emp_sub_data.get("id", "")) or str(period_data.get("employmentId", ""))
                        if emp_id and emp_id in emp_map:
                            emp = emp_map[emp_id]
                            emp["punctuality_score"] = 0.95
                            
                            features = scorer.extract_features(emp, shift, global_all_roles, mappings=env_mappings)
                            all_X.append(features)
                            all_y.append(1.0)
                            
                            # Time Decay / Recency Weighting
                            days_ago = (datetime.now() - reg_dt).days
                            if days_ago <= 60:
                                all_X.append(features)
                                all_y.append(1.0)
                            total_samples += 1
                        else:
                             msgs_dropped_id += 1
                    except: continue
                
                print(f"DEBUG: Company {primary_id}: Periods={msgs_total}, Dropped(ID Bad)={msgs_dropped_id}")
                    
            except: continue

        if not all_X:
            update_status(message="No valid training samples found.", progress=1.0, phase="IDLE")
            set_running(False)
            return

        # 3. Train Global Model
        update_status("Stochastic Gradient Descent in progress...", 0.85, "TRAINING", log=f"Training Neural Scorer on {len(all_X)} samples...")
        
        # Shuffle data before training to ensure proper validation split distribution
        indices = np.arange(len(all_X))
        np.random.shuffle(indices)
        X_shuffled = np.array(all_X)[indices]
        y_shuffled = np.array(all_y)[indices]
        
        metrics = scorer.train(X_shuffled, y_shuffled)
        
        final_loss = metrics.get("loss", 0.0)
        val_loss = metrics.get("val_loss", 0.0)
        val_accuracy = metrics.get("val_accuracy", 0.0)
        
        update_status("Persisting updated weights to GCS...", 0.95, log=f"Training completed. Val Loss: {val_loss:.4f}, Val Acc: {val_accuracy:.4f}")
        scorer.save_weights()

        update_status(
            message="Global AI Brain Updated", 
            progress=1.0, 
            phase="IDLE", 
            log="Pipeline completed successfully. Brain is hot.", 
            details={
                "loss": float(final_loss),
                "val_loss": float(val_loss),
                "accuracy": float(val_accuracy),
                "dataset_size": len(all_X),
                "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        set_running(False)
        
    except Exception as e:
        print(f"Global Training Error: {e}")
        update_status(message=f"Error: {str(e)}", phase="IDLE")
        set_running(False)

@router.post("/retrain")
def retrain_model(req: RetrainRequest, background_tasks: BackgroundTasks, environment: str = Depends(verify_hmac)):
    if get_status()["status"] == "running":
        return {"status": "busy", "message": "Global training is already in progress."}
    
    set_running(True)
    update_status(message="Initializing Global Brain...", progress=0.0, phase="IDLE")
    
    background_tasks.add_task(run_global_training)
    return {"status": "started", "message": "Global Training started."}

@router.post("/reset")
def reset_model(environment: str = Depends(verify_hmac)):
    """Hard Reset: Deletes model weights and restarts from scratch."""
    scorer = NeuralScorer()
    success = scorer.reset_weights()
    if success:
         return {"status": "success", "message": "Model weights erased. Brain is blank."}
    else:
         raise HTTPException(status_code=500, detail="Failed to reset model.")
