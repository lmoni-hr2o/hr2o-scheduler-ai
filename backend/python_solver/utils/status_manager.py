from datetime import datetime
from utils.datastore_helper import get_db
import json

# Global status key in Datastore
STATUS_KEY = "SystemStatus_Global"

def _get_raw_status():
    """Reads the current status from Datastore (Read-Only)."""
    try:
        client = get_db().client
        key = client.key("SystemStatus", STATUS_KEY)
        entity = client.get(key)
        if entity:
            return dict(entity)
    except Exception as e:
        print(f"Warning: Could not fetch raw status: {e}")
        
    return {
        "status": "idle",
        "progress": 0.0,
        "message": "Engine Ready (ReadOnly Mode)",
        "phase": "IDLE",
        "logs": "[]",
        "details": "{}",
        "last_updated": datetime.now()
    }

def update_status(message: str = None, progress: float = None, phase: str = None, log: str = None, details: dict = None):
    # DISABLED: Read-only mode active.
    print(f"STATUS UPDATE (No write): {message} - {progress}%")

def set_running(is_running: bool):
    # DISABLED: Read-only mode active.
    print(f"SET RUNNING (No write): {is_running}")

def get_status():
    """Returns the current status (Read-Only)."""
    raw = _get_raw_status()
    try:
        return {
            "status": raw.get("status", "idle"),
            "progress": float(raw.get("progress", 0.0)),
            "message": raw.get("message", "N/A"),
            "phase": raw.get("phase", "IDLE"),
            "logs": json.loads(raw.get("logs", "[]")),
            "details": json.loads(raw.get("details", "{}")),
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
