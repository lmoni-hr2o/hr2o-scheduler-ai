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
    """Deprecated."""
    return {"status": "deprecated"}

def discover_unique_environments():
    """Returns all discovered companies from Datastore."""
    results = []
    # Simple scan of known namespaces
    for ns in ["OVERCLEAN", "OVERFLOW", "default"]:
        try:
            client = get_db(namespace=ns).client
            # Fetch Companies
            query = client.query(kind="Company")
            for entity in query.fetch():
                data = dict(entity)
                # Handle numeric (id) or string (name) keys safely
                safe_id = str(entity.key.id_or_name)
                results.append({
                    "id": safe_id,
                    "name": data.get("name", safe_id),
                    "namespace": ns,
                    "is_active": True
                })
        except: pass
    return results

@router.get("/environments")
def get_environments():
    """Returns a list of all discovered companies (ID and Name) with metadata."""
    envs = discover_unique_environments()
    return {"environments": envs, "count": len(envs)}

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
                 if diff.total_seconds() > 300:
                     print(f"DEBUG: Stale training status detected in retrain ({diff.total_seconds()}s). Auto-unlocking.")
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

@router.delete("/profile")
def delete_profile(environment: str = Depends(verify_hmac)):
    """Debug: Deletes the Demand Profile to force a fresh relearn"""
    client = get_db().client
    key = client.key("DemandProfile", environment)
    client.delete(key)
    return {"status": "success", "message": f"Demand Profile deleted by USER for {environment}"}

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
        query_clean = client_clean.query(kind='Period')
        res_clean = list(query_clean.fetch(limit=1))
        messages.append(f"OVERCLEAN Period count: {len(res_clean)}")
        if res_clean: messages.append(f"Sample: {dict(res_clean[0])}")
        
        # 3. OVERFLOW
        client_flow = datastore.Client(namespace="OVERFLOW")
        query_flow = client_flow.query(kind='Period')
        res_flow = list(query_flow.fetch(limit=1))
        messages.append(f"OVERFLOW Period count: {len(res_flow)}")
            
    except Exception as e:
        messages.append(f"CRITICAL ERROR: {str(e)}")
    
    return {"logs": messages}
