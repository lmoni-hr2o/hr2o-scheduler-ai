from datetime import datetime
from utils.datastore_helper import get_db
import json

# Global status key in Datastore
STATUS_KEY = "SystemStatus_Global"

def _get_raw_status():
    client = get_db().client
    key = client.key("SystemStatus", STATUS_KEY)
    entity = client.get(key)
    if entity:
        return dict(entity)
    return {
        "status": "idle",
        "progress": 0.0,
        "message": "Engine Ready",
        "phase": "IDLE",
        "logs": "[]",
        "details": "{}"
    }

def update_status(message: str = None, progress: float = None, phase: str = None, log: str = None, details: dict = None):
    client = get_db().client
    key = client.key("SystemStatus", STATUS_KEY)
    
    # Use a transaction for atomic update if possible, but for status a simple put is usually okay
    status = _get_raw_status()
    
    if message: status["message"] = message
    if progress is not None: status["progress"] = float(progress)
    if phase: status["phase"] = phase
    
    if log:
        logs = json.loads(status.get("logs", "[]"))
        ts = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{ts}] {log}")
        if len(logs) > 50: logs.pop(0)
        status["logs"] = json.dumps(logs)
        
    if details:
        current_details = json.loads(status.get("details", "{}"))
        current_details.update(details)
        status["details"] = json.dumps(current_details)
    
    from google.cloud import datastore
    entity = datastore.Entity(key=key, exclude_from_indexes=['logs', 'details'])
    entity.update(status)
    client.put(entity)

def get_status():
    raw = _get_raw_status()
    # Deserializzazione per il frontend
    return {
        "status": raw.get("status", "idle"),
        "progress": float(raw.get("progress", 0.0)),
        "message": raw.get("message", "N/A"),
        "phase": raw.get("phase", "IDLE"),
        "logs": json.loads(raw.get("logs", "[]")),
        "details": json.loads(raw.get("details", "{}"))
    }

def set_running(is_running: bool):
    client = get_db().client
    key = client.key("SystemStatus", STATUS_KEY)
    status = _get_raw_status()
    
    status["status"] = "running" if is_running else "complete"
    if is_running:
        status["logs"] = "[]"
        status["progress"] = 0.0
    else:
        status["phase"] = "IDLE"
        status["progress"] = 1.0
        
    from google.cloud import datastore
    entity = datastore.Entity(key=key, exclude_from_indexes=['logs', 'details'])
    entity.update(status)
    client.put(entity)
