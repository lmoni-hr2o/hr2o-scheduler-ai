from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from utils.datastore_helper import get_db
import numpy as np
from typing import List, Optional, Dict, Any
from scorer.model import NeuralScorer
from solver.logger import save_log, get_all_logs
from utils.security import verify_hmac
import json
from google.cloud import datastore

router = APIRouter(prefix="/training", tags=["Training"])

# Global State for Progress Tracking
TRAINING_STATUS = {
    "status": "idle", # idle, running, complete, error
    "progress": 0.0,
    "message": "Ready to train",
    "details": {}
}

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
    return TRAINING_STATUS

@router.get("/model-stats")
def get_model_stats(environment: str = Depends(verify_hmac)):
    """Exposes internal AI metrics for the Developer Hub."""
    scorer = NeuralScorer()
    return scorer.get_stats()

# Simple in-memory cache for discovered environments
DISCOVERED_ENVS_CACHE = {"envs": [], "last_updated": 0}
import time

def discover_unique_environments():
    """Helper to find all environments across namespaces using projections."""
    global DISCOVERED_ENVS_CACHE
    
    # Cache for 60 seconds
    if time.time() - DISCOVERED_ENVS_CACHE["last_updated"] < 60:
        return DISCOVERED_ENVS_CACHE["envs"]

    all_envs = set()
    try:
        for ns in [None, "OVERCLEAN"]:
            client = get_db(namespace=ns).client
            # Scan LearningLog with projection (much faster)
            try:
                query = client.query(kind='LearningLog', projection=['environment'])
                all_envs.update([e.get('environment') for e in query.fetch() if e.get('environment')])
            except Exception as e:
                print(f"DEBUG: LearningLog projection failed for ns {ns}: {e}")
                # Fallback to full fetch if projection fails (e.g. missing index)
                query = client.query(kind='LearningLog')
                all_envs.update([e.get('environment') for e in query.fetch() if e.get('environment')])

            # Scan Period with projection
            try:
                query = client.query(kind='Period', projection=['environment'])
                all_envs.update([e.get('environment') for e in query.fetch() if e.get('environment')])
            except Exception as e:
                print(f"DEBUG: Period projection failed for ns {ns}: {e}")
                query = client.query(kind='Period')
                all_envs.update([e.get('environment') for e in query.fetch() if e.get('environment')])
    except Exception as e:
        print(f"Environment discovery error: {e}")
        
    res = list(all_envs)
    DISCOVERED_ENVS_CACHE = {"envs": res, "last_updated": time.time()}
    return res

@router.get("/environments")
def get_environments(environment: str = Depends(verify_hmac)):
    """Returns a list of all discovered environments/companies."""
    envs = discover_unique_environments()
    return {"environments": envs, "count": len(envs)}

@router.post("/log-feedback")
def log_feedback(req: FeedbackRequest, environment: str = Depends(verify_hmac)):
    """
    Logs user corrections to Google Cloud Datastore.
    """
    save_log(req.action, req.selected_id, req.rejected_id, req.shift_data, environment)
    return {"status": "success", "message": f"Feedback stored in Datastore for {environment}"}

def run_global_training():
    """
    Background Task: Discovers environments from logs, aggregates data, and trains the Global Model.
    """
    global TRAINING_STATUS
    TRAINING_STATUS = {"status": "running", "progress": 0.0, "message": "Initializing Global Brain...", "details": {}}
    
    try:
        # Use our helper for unified client management
        db = get_db()
        
        # 1. Discover environments from LearningLog entities
        TRAINING_STATUS["message"] = "Discovering environments from logs..."
        
        # Try both default and OVERCLEAN namespace for logs
        all_logs_entities = []
        for ns in [None, "OVERCLEAN"]:
            print(f"DEBUG: Checking for logs in namespace: {ns}")
            client = get_db(namespace=ns).client
            query = client.query(kind='LearningLog')
            results = list(query.fetch())
            if results:
                print(f"DEBUG: Found {len(results)} logs in namespace {ns}")
                all_logs_entities.extend(results)
        
        if not all_logs_entities:
            TRAINING_STATUS = {"status": "complete", "progress": 1.0, "message": "No training logs found to learn from in any namespace.", "details": {}}
            return
            
        unique_envs = list(set([entity.get('environment') for entity in all_logs_entities if entity.get('environment')]))
        total_envs = len(unique_envs)
        
        print(f"DEBUG: Found {total_envs} environments from logs: {unique_envs}")

        if total_envs == 0:
            TRAINING_STATUS = {"status": "complete", "progress": 1.0, "message": "No valid environments found in logs.", "details": {}}
            return

        all_X = []
        all_y = []
        
        # 2. Iterate and Aggregate
        scorer = NeuralScorer()
        scorer.load_weights()
        
        from routers.agent import get_employment, get_activities
        
        # Group logs by environment
        logs_by_env = {}
        for entity in all_logs_entities:
            env = entity.get('environment')
            if env:
                if env not in logs_by_env:
                    logs_by_env[env] = []
                log_dict = dict(entity)
                if 'shift_data' in log_dict and isinstance(log_dict['shift_data'], str):
                    try:
                        log_dict['shift_data'] = json.loads(log_dict['shift_data'])
                    except: pass
                logs_by_env[env].append(log_dict)

        for i, env_id in enumerate(unique_envs):
            TRAINING_STATUS["message"] = f"Learning from {env_id} ({i+1}/{total_envs})..."
            TRAINING_STATUS["progress"] = (i / total_envs) * 0.8
            
            try:
                env_logs = logs_by_env.get(env_id, [])
                employees = get_employment(env_id)
                activities = get_activities(env_id)
                
                emp_map = {e.id: e.dict() for e in employees}
                all_roles = list(set([e.role for e in employees] + [a.name for a in activities]))
                
                for log in env_logs:
                    shift = log.get("shift_data", {})
                    # Positive Sample
                    if log["selected_id"] in emp_map:
                        all_X.append(scorer.extract_features(emp_map[log["selected_id"]], shift, all_roles))
                        all_y.append(1.0)
                    # Negative Sample
                    if log.get("rejected_id") and log["rejected_id"] in emp_map:
                        all_X.append(scorer.extract_features(emp_map[log["rejected_id"]], shift, all_roles))
                        all_y.append(0.0)
            except: continue

        if not all_X:
            TRAINING_STATUS = {"status": "complete", "progress": 1.0, "message": "No valid training samples found.", "details": {}}
            return

        # 3. Train Global Model
        TRAINING_STATUS["message"] = f"Training on {len(all_X)} global samples..."
        TRAINING_STATUS["progress"] = 0.9
        
        final_loss = scorer.train(np.array(all_X), np.array(all_y))
        scorer.save_weights()

        TRAINING_STATUS = {
            "status": "complete",
            "progress": 1.0,
            "message": f"Global Training Complete. Loss: {final_loss:.4f}",
            "details": {"samples": len(all_X)}
        }
        
    except Exception as e:
        print(f"Global Training Error: {e}")
        TRAINING_STATUS["status"] = "error"
        TRAINING_STATUS["message"] = f"Error: {str(e)}"

@router.post("/retrain")
def retrain_model(background_tasks: BackgroundTasks, environment: str = Depends(verify_hmac)):
    if TRAINING_STATUS["status"] == "running":
        return {"status": "busy", "message": "Global training is already in progress."}
    background_tasks.add_task(run_global_training)
    return {"status": "started", "message": "Global Training started."}
