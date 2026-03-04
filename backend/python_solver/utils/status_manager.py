import os
import json
from datetime import datetime, timedelta
from utils.datastore_helper import get_db

# Global status key in Datastore
STATUS_KEY = "SystemStatus_Global"
# Standard TTL for a lock to be considered stale
LOCK_TTL_MINUTES = 10

def get_worker_id():
    """Returns a unique ID for this instance."""
    return os.getenv("K_REVISION", os.getenv("HOSTNAME", "local_worker"))

def _get_raw_status(namespace: str = None):
    """Reads the current status from Datastore."""
    try:
        client = get_db(namespace=namespace).client
        key = client.key("SystemStatus", STATUS_KEY, namespace=namespace)
        entity = client.get(key)
        if entity:
            return dict(entity)
    except Exception as e:
        print(f"Warning: Could not fetch raw status: {e}")
        
    return {
        "status": "idle",
        "progress": 0.0,
        "message": "Engine Ready",
        "phase": "IDLE",
        "logs": "[]",
        "details": "{}",
        "worker_id": None,
        "last_updated": datetime.now()
    }

def update_status(message: str = None, progress: float = None, phase: str = None, log: str = None, details: dict = None, namespace: str = None):
    """Updates the global system status with current progress. SKIPPED in Read-Only Mode."""
    if os.getenv("READ_ONLY_MODE", "true").lower() == "true":
        return
    try:
        # ... existing logic ...
        client = get_db(namespace=namespace).client
        key = client.key("SystemStatus", STATUS_KEY, namespace=namespace)
        
        with client.transaction():
            entity = client.get(key)
            if not entity:
                from google.cloud import datastore
                entity = datastore.Entity(key=key, exclude_from_indexes=["logs", "details"])
            
            if message is not None: entity["message"] = message
            if progress is not None: entity["progress"] = float(progress)
            if phase is not None: entity["phase"] = phase
            if details is not None: entity["details"] = json.dumps(details)
            
            if log is not None:
                current_logs = json.loads(entity.get("logs", "[]"))
                current_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {log}")
                entity["logs"] = json.dumps(current_logs[-50:]) # Keep last 50 logs
                
            entity["last_updated"] = datetime.now()
            entity["worker_id"] = get_worker_id()
            client.put(entity)
            
    except Exception as e:
        print(f"ERROR updating status: {e}")

def set_running(is_running: bool, force: bool = False, namespace: str = None):
    """
    Sets the system status to 'busy' or 'idle'. SKIPPED in Read-Only Mode.
    """
    if os.getenv("READ_ONLY_MODE", "true").lower() == "true":
        return True
    try:
        client = get_db(namespace=namespace).client
        key = client.key("SystemStatus", STATUS_KEY, namespace=namespace)
        worker_id = get_worker_id()
        
        with client.transaction():
            entity = client.get(key)
            if not entity:
                from google.cloud import datastore
                entity = datastore.Entity(key=key)
            
            current_status = entity.get("status", "idle")
            current_worker = entity.get("worker_id")
            last_upd = entity.get("last_updated")
            
            # TTL check
            is_stale = False
            if last_upd and isinstance(last_upd, datetime):
                 # Handle timezone-aware vs naive comparison
                 from datetime import timezone
                 now = datetime.now(timezone.utc) if last_upd.tzinfo else datetime.now()
                 if now - last_upd > timedelta(minutes=LOCK_TTL_MINUTES):
                     is_stale = True
            if is_running:
                # Try to acquire lock
                if current_status == "busy" and current_worker != worker_id and not is_stale and not force:
                    print(f"Lock active by worker {current_worker}. Cannot acquire.")
                    return False
                
                entity.update({
                    "status": "busy",
                    "worker_id": worker_id,
                    "last_updated": datetime.now(),
                    "progress": 0.0,
                    "phase": "STARTED",
                    "logs": "[]"
                })
                client.put(entity)
                return True
            else:
                # Try to release lock
                if current_worker == worker_id or is_stale or force:
                    entity.update({
                        "status": "idle",
                        "worker_id": None,
                        "last_updated": datetime.now()
                    })
                    client.put(entity)
                    return True
                else:
                    print(f"Worker {worker_id} tried to clear lock owned by {current_worker}")
                    return False
    except Exception as e:
        print(f"ERROR setting running state: {e}")
        return False

def get_status(namespace: str = None):
    """Returns the current status formatted for the API."""
    raw = _get_raw_status(namespace=namespace)
    try:
        return {
            "status": raw.get("status", "idle"),
            "progress": float(raw.get("progress", 0.0)),
            "message": raw.get("message", "N/A"),
            "phase": raw.get("phase", "IDLE"),
            "logs": json.loads(raw.get("logs", "[]")),
            "details": json.loads(raw.get("details", "{}")),
            "worker_id": raw.get("worker_id"),
            "last_updated": str(raw.get("last_updated"))
        }
    except Exception:
        return {
            "status": "idle", 
            "progress": 0.0, 
            "message": "Error decoding status", 
            "phase": "IDLE", 
            "logs": [], 
            "details": {}
        }
