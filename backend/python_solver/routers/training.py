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
# from utils.mapping_helper import mapper # Removed
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
    
    # client.put(entity)
    return {"status": "success", "message": "READ-ONLY: Config save disabled"}

class FeedbackRequest(BaseModel):
    action: str
    selected_id: str
    rejected_id: Optional[str] = None
    shift_data: Optional[dict] = {}

class ScheduleFeedbackRequest(BaseModel):
    environment: str
    schedule: List[Dict[str, Any]]

class RetrainRequest(BaseModel):
    company_id: Optional[str] = None

@router.post("/feedback")
def submit_feedback(req: ScheduleFeedbackRequest, background_tasks: BackgroundTasks):
    """
    Submits a finalized schedule as training feedback.
    The AI will learn from the assignments in this schedule.
    """
    background_tasks.add_task(run_incremental_training, req.environment, req.schedule)
    return {"status": "success", "message": "Feedback received. Incremental training started."}

def run_incremental_training(environment: str, schedule: List[Dict[str, Any]]):
    """
    Background Task: Incremental Training.
    Updates the model based on a single schedule's assignments.
    """
    print(f"DEBUG: Starting Incremental Training for {environment}...")
    try:
        scorer = NeuralScorer()
        scorer.refresh_if_needed()
        
        all_X = []
        all_y = []
        
        # 1. Extract assignments as positive samples
        for s in schedule:
            if s.get("employee_id") and not s.get("is_unassigned"):
                # We need the full employee object to extract features.
                # However, the feedback might only contain basic info.
                # We'll fetch the employee from Datastore to be safe.
                eid = s["employee_id"]
                client = get_db(namespace=environment).client
                emp_entity = client.get(client.key("Employment", eid))
                
                if emp_entity:
                    emp_data = dict(emp_entity)
                    emp_data["id"] = eid
                    
                    features = scorer.extract_features(emp_data, s)
                    all_X.append(features)
                    all_y.append(1.0)
                    
                    # Also add a negative sample: same shift, random different person
                    # (Simplified negative sampling)
                    # For a truly effective learning, we need real 'alternatives'.
        
        if all_X:
            X = np.array(all_X)
            y = np.array(all_y)
            # Fast incremental step: 2 epochs
            scorer.train(X, y, epochs=2, validation_split=0.0)
            scorer.save_weights()
        else:
            pass
            
    except Exception as e:
        print(f"ERROR in Incremental Training: {e}")

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
    """Deprecated."""
    return {"status": "deprecated"}

def discover_unique_environments():
    """Returns all discovered companies from Datastore by scanning all namespaces."""
    client = get_db().client
    results = []
    
    # 1. Find all active namespaces
    namespaces = []
    try:
        ns_query = client.query(kind="__namespace__")
        ns_query.keys_only()
        namespaces = [str(ns.key.id_or_name) for ns in ns_query.fetch()]
    except Exception as e:
        print(f"Error fetching namespaces: {e}")
        namespaces = ["OVERCLEAN", "OVERFLOW", None]

    # 2. Search for Companies in each namespace
    seen_ids = set()
    for ns in namespaces:
        # Skip architectural namespaces
        if ns and ns.startswith("__"): continue
        
        try:
            # Fetch Companies in this namespace
            query = client.query(kind="Company", namespace=ns)
            for entity in query.fetch():
                data = dict(entity)
                safe_id = str(entity.key.id_or_name)
                
                # Use a unique key for the result (id + namespace if needed, but id is usually unique enough)
                if safe_id in seen_ids: continue
                
                # Filter out empty companies
                # FIX: Default to 0 now - if we haven't synced it yet to know the count, don't show it.
                emp_count = data.get("active_employees_count", 0)
                
                # Only add if it has employees
                if emp_count > 0:
                    results.append({
                        "id": safe_id,
                        "name": data.get("name", safe_id),
                        "namespace": ns,
                        "active_employees_count": emp_count,
                        "is_active": True
                    })
                    seen_ids.add(safe_id)
        except Exception as e:
            print(f"Error scanning namespace {ns}: {e}")
            
    return results

@router.get("/environments")
def get_environments():
    """Returns a list of all discovered companies (ID and Name) with metadata."""
    envs = discover_unique_environments()
    # Filter only those with employees (already filtered in discover but double check for safety)
    valid_envs = [e for e in envs if e.get("active_employees_count", 0) > 0]
    return {"environments": valid_envs, "count": len(valid_envs)}

@router.on_event("startup")
def startup_event():
    """Initializes the system."""
    import threading
    # Safety: Clear any stale "running" locks from previous crashed instances
    set_running(False)
    # We no longer trigger global training on startup to ensure fast cold boot
    pass


def run_global_training():
    """
    Background Task: Global Training.
    Discovers environments from Datastore and trains the model.
    """
    set_running(True)
    update_status(message="Starting Global AI Pipeline", progress=0.05, phase="MAPPING", log="Initializing Environment Ingestion Engine...")
    
    try:
        # 1. Discover Environments via Helper
        envs = discover_unique_environments()
        if not envs:
            print("INFO: No environments found for training.")
            update_status("No data found.", 1.0, "IDLE")
            set_running(False)
            return

        # 2. Setup Scorer
        from utils.date_utils import parse_date, format_date_iso
        from scorer.model import NeuralScorer
        import numpy as np
        
        scorer = NeuralScorer()
        scorer.load_weights()
        
        all_X = []
        all_y = []
        total_p_envs = len(envs)
        
        # 3. Iterate and Aggregate
        for i, env_meta in enumerate(envs):
            primary_id = env_meta["id"]
            ns = primary_id # The namespace IS the company ID now
            
            update_status(
                message=f"Training on {env_meta['name']}",
                progress=0.1 + (i / total_p_envs) * 0.7,
                phase="EXTRACTION",
                log=f"Extracting features from: {env_meta['name']} ({ns})..."
            )
            
            try:
                client = get_db(namespace=ns).client
                
                # A. Fetch Employees
                emp_query = client.query(kind="Employment")
                valid_employees = {}
                for e_entity in emp_query.fetch():
                    ed = dict(e_entity)
                    # Maps to internal model
                    emp_obj = Employment(
                        id=e_entity.key.name,
                        name=ed.get("name"),
                        fullName=ed.get("fullName"),
                        role=ed.get("role", "worker"),
                        environment=ns,
                        address=ed.get("address"),
                        city=ed.get("city"),
                        bornDate=ed.get("bornDate"),
                        dtHired=ed.get("dtHired")
                    )
                    valid_employees[e_entity.key.name] = emp_obj.dict()

                if not valid_employees:
                    continue

                # B. Fetch Periods (History)
                p_query = client.query(kind="Period")
                # Optimization: Limit to recent history if needed, for now all
                raw_periods = list(p_query.fetch())
                
                # C. Extract Features
                # (Simplified logic mimicking the original but using clean dicts)
                
                for p_entity in raw_periods:
                    p = dict(p_entity)
                    
                    pid = p.get("employmentId")
                    if not pid or pid not in valid_employees:
                         continue
                         
                    emp_data = valid_employees[pid]
                    
                    # Parse Dates
                    reg_dt = parse_date(p.get("tmregister"))
                    if not reg_dt: continue
                    
                    # Construct Shift Object
                    # We need to extract role/project from nested activities dict
                    # Note: sync.py stored 'activities' as a dict or list? JSON likely.
                    act_data = p.get("activities") or {}
                    
                    role = "worker"
                    if isinstance(act_data, dict):
                        role = str(act_data.get("name") or act_data.get("code") or "worker")
                    
                    shift = {
                        "date": format_date_iso(reg_dt),
                        "start_time": "08:00", # Fallback if tmregister is just date
                        "end_time": "17:00",
                        "role": role,
                        "project": act_data.get("project") if isinstance(act_data, dict) else {},
                        "customer_address": "" # Extract if deeper in JSON
                    }
                    
                    # Positive Sample
                    emp_data["punctuality_score"] = 0.95
                    features = scorer.extract_features(emp_data, shift)
                    all_X.append(features)
                    all_y.append(1.0)
                    
                    # Negative Sample (Random)
                    import random
                    if len(valid_employees) > 1:
                        neg_id = random.choice(list(valid_employees.keys()))
                        if neg_id != pid:
                            neg_emp = valid_employees[neg_id].copy()
                            neg_emp["punctuality_score"] = 0.5
                            all_X.append(scorer.extract_features(neg_emp, shift))
                            all_y.append(0.0)

            except Exception as e:
                print(f"Error processing {primary_id}: {e}")
                continue

        if not all_X:
            update_status(message="No training data extracted.", progress=1.0, phase="IDLE")
            set_running(False)
            return

        # 4. Train
        update_status("Running Gradient Descent...", 0.9, "TRAINING", log=f"Training on {len(all_X)} samples...")
        
        indices = np.arange(len(all_X))
        np.random.shuffle(indices)
        X_shuffled = np.array(all_X)[indices]
        y_shuffled = np.array(all_y)[indices]
        
        metrics = scorer.train(X_shuffled, y_shuffled)
        scorer.save_weights()
        
        update_status(
            message="AI Training Completed", 
            progress=1.0, 
            phase="IDLE", 
            log=f"Model updated. Loss: {metrics.get('loss', 0):.4f}"
        )
        set_running(False)
        
    except Exception as e:
        print(f"Global Training Error: {e}")
        update_status(message=f"Error: {str(e)}", phase="IDLE")
        set_running(False)





@router.post("/retrain")
def retrain_model(req: RetrainRequest, background_tasks: BackgroundTasks, environment: str = Depends(verify_hmac)):
    status = get_status()
    if status["status"] == "running":
        # Check staleness
        import datetime
        last_upd = status.get("last_updated")
        is_stale = False
        if last_upd:
             if not isinstance(last_upd, datetime.datetime):
                 from utils.date_utils import parse_date
                 last_upd = parse_date(str(last_upd))
             
             if last_upd:
                 diff = datetime.datetime.now(last_upd.tzinfo) - last_upd
                 # No debug logs in production
                 if diff.total_seconds() > 300:
                     is_stale = True

        if not is_stale:
            return {"status": "busy", "message": "Global training is already in progress."}
        else:
            set_running(False)
    
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

@router.get("/profile")
def get_profile(environment: str = Depends(verify_hmac)):
    """Debug: Returns the current learned Demand Profile JSON"""
    from utils.demand_profiler import get_demand_profile
    return get_demand_profile(environment) or {}

@router.post("/migrate-history")
def run_history_migration(namespace: str = "OVERCLEAN"):
    """Maintenance: Migrates periods from root to numeric namespaces and cleans up activities."""
    from utils.history_migration import migrate_periods_to_company_namespaces
    logs = migrate_periods_to_company_namespaces(namespace)
    return {"status": "success", "logs": logs}

@router.delete("/profile")
def delete_profile(environment: str = Depends(verify_hmac)):
    """Debug: Deletes the Demand Profile to force a fresh relearn"""
    client = get_db().client
    key = client.key("DemandProfile", environment)
    # client.delete(key)
    return {"status": "success", "message": "READ-ONLY: Profile deletion disabled"}

@router.get("/ds-inspect")
def inspect_datastore():
    """Debug: Raw inspection of Datastore connectivity and data existence."""
    messages = []
    try:
        from google.cloud import datastore
        # 1. Default Namespace
        client = datastore.Client()
        query = client.query(kind='Period')
        res = list(query.fetch(limit=1))
        messages.append(f"Default NS Period count: {len(res)}")
        if res: messages.append(f"Sample: {dict(res[0])}")

        # 2. OVERCLEAN
        client_clean = datastore.Client(namespace="OVERCLEAN")
        query_act = client_clean.query(kind='Activity')
        res_act = list(query_act.fetch(limit=1))
        if res_act:
            messages.append(f"Sample Activity Keys: {list(res_act[0].keys())}")
            
            # List some with demand
            q_demand = client_clean.query(kind='Activity')
            demand_acts = []
            for a in q_demand.fetch(limit=100):
                h = a.get('hhSchedule')
                d = a.get('dailySchedule')
                if h or d:
                    demand_acts.append(f"{a.get('name')}: hh={h}, daily_len={len(d) if d else 0}")
            
            if demand_acts:
                messages.append("Activities with Demand: " + " | ".join(demand_acts[:5]))
            else:
                messages.append("No activities with demand signals found.")
        
        query_clean = client_clean.query(kind='Period')
        res_clean = list(query_clean.fetch(limit=5))
        messages.append(f"OVERCLEAN Period count: {len(res_clean)}")
        if res_clean:
            samples = [f"{p.key.name or p.key.id}: emp={p.get('employmentId')}" for p in res_clean]
            messages.append("OVERCLEAN Period sample: " + " | ".join(samples))
            messages.append(f"OVERCLEAN Period keys: {list(res_clean[0].keys())}")
            # Check if there is an 'employment' dict
            messages.append(f"OVERCLEAN Period employment field: {res_clean[0].get('employment')}")
            messages.append(f"OVERCLEAN Period activities field (RAW): {res_clean[0].get('activities')}")
            
            # Try to see if it is a list or dict
            act_field = res_clean[0].get('activities')
            if isinstance(act_field, list):
                messages.append(f"OVERCLEAN Period activities count: {len(act_field)}")
                if act_field:
                    messages.append(f"OVERCLEAN Period first activity: {act_field[0]}")
            elif isinstance(act_field, dict):
                messages.append(f"OVERCLEAN Period activities keys: {list(act_field.keys())}")
        
        # Deep Probe: Companies in OVERCLEAN root
        query_comp_root = client_clean.query(kind='Company')
        comps_root = list(query_comp_root.fetch(limit=10))
        messages.append(f"OVERCLEAN Company sample: " + " | ".join([f"{c.key.name}" for c in comps_root]))

        # Deep Probe: Employments in OVERCLEAN root
        query_emp_root = client_clean.query(kind='Employment')
        emps_root = list(query_emp_root.fetch(limit=10))
        messages.append(f"OVERCLEAN Employment sample: " + " | ".join([f"{e.key.name}->{e.get('environment')}" for e in emps_root]))
        
        # 4. OVERCLEAN DEMAND PROFILE (Numeric)
        eid_num = "5629499534213120"
        eid_str = "OVERCLEAN"
        client_global = datastore.Client()
        
        for eid in [eid_num, eid_str]:
            key_p = client_global.key("DemandProfile", eid)
            ent_p = client_global.get(key_p)
            if ent_p:
                messages.append(f"Profile found for {eid} (last_updated: {ent_p.get('last_updated')})")
                import json
                try:
                    p_data = json.loads(ent_p.get("data_json", "{}"))
                    messages.append(f"Profile {eid} activity count: {len(p_data)}")
                    p_keys = list(p_data.keys())
                    messages.append(f"Profile {eid} sample keys: {p_keys[:10]}")
                    
                    # Print DOW coverage for first 3 activities
                    for k in p_keys[:3]:
                        dows = list(p_data[k].keys())
                        messages.append(f"Activity {k} DOWs: {dows}")
                except Exception as e_json:
                    messages.append(f"Profile {eid} JSON ERROR: {e_json}")
            else:
                messages.append(f"Profile NOT FOUND for {eid}")

        # 6. SCAN ALL NAMESPACES FOR PERIODS
        q_ns = client.query(kind="__namespace__")
        q_ns.keys_only()
        all_nss = [str(e.key.id_or_name) for e in q_ns.fetch()]
        
        counts = []
        for ns_id in all_nss:
            if ns_id.startswith("__"): continue
            q_p = client.query(kind="Period", namespace=ns_id)
            count = len(list(q_p.fetch(limit=100)))
            if count > 0:
                counts.append(f"NS {ns_id}: {count} periods")
        
        if counts:
            messages.append("Global Period Scan: " + " | ".join(counts))
        else:
            messages.append("Global Period Scan: NO PERIODS FOUND ANYWHERE")
            
    except Exception as e:
        messages.append(f"CRITICAL ERROR: {str(e)}")
    
    return {"logs": messages}
class LearnDemandRequest(BaseModel):
    company_id: Optional[str] = None
    environment: Optional[str] = None
    namespace: Optional[str] = None

@router.post("/learn-demand")
def learn_demand(request: LearnDemandRequest):
    """
    Triggers the DemandProfiler to learn from ALL available history in the specified namespace.
    If 'namespace' is provided, it overrides the environment-based namespace.
    """
    target_env = request.namespace or request.environment or request.company_id
    if not target_env:
        raise HTTPException(status_code=400, detail="Missing company_id, environment, or namespace.")
        
    try:
        from utils.demand_profiler import DemandProfiler
        from google.cloud import datastore
        
        client = get_db(namespace=target_env).client
        
        # 1. Identify Active Employees
        # We learn only from staff who are still in the company (not dismissed)
        emp_query = client.query(kind="Employment")
        active_emp_ids = set()
        for e in emp_query.fetch():
            if not e.get("dtDismissed"): # No dismissal date means active
                active_emp_ids.add(str(e.key.id_or_name))
        
        # 2. Identify Active Activities
        # We collect BOTH IDs and Codes/Names to ensure matching with historical data
        act_query = client.query(kind="Activity")
        active_act_keys = set()
        legacy_years = ["2020", "2021", "2022", "2023", "2024"]
        for a in act_query.fetch():
            name = str(a.get("name") or "").upper()
            code = str(a.get("code") or "")
            aid = str(a.key.id_or_name)
            
            if not any(year in name for year in legacy_years):
                active_act_keys.add(aid)
                if code: active_act_keys.add(code)
                if name: active_act_keys.add(name)
        
        print(f"DEBUG: Learning Demand for {target_env}. ActiveEmps: {len(active_emp_ids)}, ActiveActKeys: {len(active_act_keys)}")

        # 3. Fetch All Periods and Learn
        query = client.query(kind="Period")
        raw_periods = list(query.fetch())
        
        if not raw_periods:
            return {"status": "warning", "message": f"No periods found in namespace {target_env}. Learning skipped."}
            
        profiler = DemandProfiler(target_env)
        # Learn with filters
        profiler.learn_from_periods(
            raw_periods, 
            active_employee_ids=active_emp_ids, 
            active_activity_ids=active_act_keys
        )
        profiler.save_to_datastore()
        
        return {
            "status": "success", 
            "message": f"Demand Profile learned from {len(raw_periods)} periods for {target_env}.",
            "active_employees_filtered": len(active_emp_ids),
            "active_activities_filtered": len(active_act_keys),
            "profile_patterns_found": len(profiler.profile)
        }
    except Exception as e:
        print(f"Error in learn_demand: {e}")
        raise HTTPException(status_code=500, detail=str(e))
