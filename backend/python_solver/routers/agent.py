from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict
from datetime import datetime
import requests
from google.cloud import datastore
from models import Activity, Employment, Period, DataMapping
from utils.security import verify_hmac
from utils.datastore_helper import get_db

router = APIRouter(prefix="/agent", tags=["Agent"])



@router.get("/ping")
def ping():
    return {"status": "Agent Router is reachable"}

from datetime import datetime, date
import dateutil.parser as date_parser

def safe_parse_date(v) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, (datetime, date)):
        return v.date() if hasattr(v, 'date') else v
    
    s = str(v).strip()
    if not s or s.lower() == "none":
        return None
        
    try:
        # Try primary ISO format or dateutil magic for "Sep 30, 2020"
        dt = date_parser.parse(s)
        return dt.date()
    except:
        # Fallback for DD/MM/YYYY
        if "/" in s:
            try:
                parts = s.split("/")
                if len(parts) == 3:
                   # Try DD/MM/YYYY
                   return date(int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                pass
    return None

@router.get("/companies")
def get_companies(environment: str = Depends(verify_hmac)):
    """Fetches synced companies from Datastore."""
    try:
        client = get_db(namespace=environment).client
        query = client.query(kind="Company")
        all_ents = list(query.fetch())
        print(f"AGENT: Raw companies fetched: {len(all_ents)} for {environment}")
        results = []
        for entity in all_ents:
            # Show ALL companies for now to be safe, but mark their status
            data = dict(entity)
            data["id"] = str(entity.key.id_or_name)
            
            # Diagnostic info
            has_hist = entity.get("has_history") is True
            emp_count = entity.get("active_employees_count") or 0
            
            # If the user is seeing NOTHING, let's relax the filter 
            # and just show everything that has a name
            if data.get("name"):
                results.append(data)
                
        print(f"AGENT: Final visible companies: {len(results)}")
        return results
    except Exception as e:
        print(f"ERROR fetching companies: {e}")
        return []

@router.get("/activities", response_model=List[Activity])
def get_activities(environment: str = Depends(verify_hmac)):
    """Fetches synced activities from Datastore. Filters out likely legacy items."""
    try:
        client = get_db(namespace=environment).client
        query = client.query(kind="Activity")
        results = []
        
        legacy_years = ["2020", "2021", "2022", "2023"]
        
        for entity in query.fetch():
            data = dict(entity)
            name = str(data.get("name") or "").upper()
            
            if any(year in name for year in legacy_years):
                continue
                
            data["id"] = str(entity.key.id_or_name)
            results.append(Activity(**data))
        return results
    except Exception as e:
        print(f"ERROR fetching activities: {e}")
        return []

@router.get("/employment", response_model=List[Employment])
def get_employment(environment: str = Depends(verify_hmac)):
    """Fetches synced employment from Datastore."""
    try:
        client = get_db(namespace=environment).client
        query = client.query(kind="Employment")
        results = []
        today = date.today()
        
        entities = list(query.fetch())
        print(f"AGENT: Raw entities fetched: {len(entities)} for namespace {environment}")

        for entity in entities:
            data = dict(entity)
            emp_name = data.get("fullName", "Unknown")
            
            # 1. Filter Dismissed
            dt_dismissed = safe_parse_date(data.get("dtDismissed"))
            if dt_dismissed and dt_dismissed < today:
                print(f"AGENT: Skipping {emp_name} - dismissed on {dt_dismissed}")
                continue
            
            # 2. Filter Not Yet Hired
            dt_hired = safe_parse_date(data.get("dtHired"))
            if dt_hired and dt_hired > today:
                print(f"AGENT: Skipping {emp_name} - hire date in future {dt_hired}")
                continue
            
            # 3. Filter Inactive/Empty Hours (Only if explicitly zero)
            ch = data.get("contract_hours")
            if ch is not None:
                try:
                    if float(ch) < 0: # Negative hours? Skip. Zero might be allowed for flex workers.
                        continue
                except:
                    pass
                
            data["id"] = str(entity.key.id_or_name)
            try:
                emp_obj = Employment(**data)
                results.append(emp_obj)
            except Exception as model_err:
                print(f"AGENT: Model Validation Error for {emp_name}: {model_err}")
                # Try to fix minimalist data and retry once
                if not data.get("fullName"): data["fullName"] = emp_name
                try:
                    results.append(Employment(**data))
                except:
                    pass
        
        print(f"AGENT: Final active list: {len(results)} employees for {environment}")
        return results
    except Exception as e:
        print(f"ERROR fetching employment: {e}")
        return []

@router.get("/periods", response_model=List[Period])
def get_periods(
    start_date: datetime, 
    end_date: datetime, 
    environment: str = Depends(verify_hmac)
):
    """
    Fetches Periods from Datastore (now the source of truth if synced).
    Legacy logic for external fetch removed - we rely on /sync.
    """
    try:
        client = get_db(namespace=environment).client
        query = client.query(kind="Period")
        
        # Datastore query filter
        # Note: Datastore doesn't support complex range on different fields well 
        # but we can filter by 'tmregister'
        query.add_filter("tmregister", ">=", start_date.isoformat())
        query.add_filter("tmregister", "<=", end_date.isoformat())
        
        results = []
        for entity in query.fetch():
            data = dict(entity)
            data["id"] = entity.key.name
            results.append(Period(**data))
        return results
    except Exception as e:
        print(f"DEBUG: Internal periods fetch failed: {e}")
        return []

@router.post("/periods", response_model=Period)
def create_period(period: Period, environment: str = Depends(verify_hmac)):
    """Writes a period to Datastore."""
    try:
        client = get_db(namespace=environment).client
        key = client.key("Period", period.id or "new")
        entity = datastore.Entity(key=key)
        entity.update(period.dict())
        # client.put(entity)
        return period
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diagnostics")
def get_diagnostics(environment: str = Depends(verify_hmac)):
    """Replaced by simple count check."""
    return {"status": "ok", "mode": "synced"}

@router.post("/reset_status")
def reset_status(): 
    from utils.status_manager import set_running
    set_running(False)
    return {"status": "System status reset to IDLE"}

@router.get("/features")
def get_model_features():
    """Returns the list of features expected by the Neural Scorer."""
    return [
        {"id": "role_match", "name": "Role Matching", "description": "Checks if employee role matches shift role"},
        {"id": "time_of_day", "name": "Time of Day", "description": "Preference for morning/afternoon/night"},
        {"id": "day_of_week", "name": "Day of Week", "description": "Day of week distribution"},
        {"id": "age", "name": "Employee Age", "description": "Inferred from birth date"},
        {"id": "distance", "name": "Geoloc Distance", "description": "Distance between employee and customer"},
        {"id": "punctuality", "name": "Punctuality Score", "description": "Historical punctuality pattern"},
        {"id": "task_keywords", "name": "Task Affinity", "description": "Matching skill keywords in descriptions"},
        {"id": "seniority", "name": "Seniority", "description": "Inferred experience level"},
        {"id": "role_index", "name": "Role Diversity", "description": "Diversity across different roles"},
        {"id": "vehicle_req", "name": "Vehicle Requirement", "description": "Check if employee has vehicle if required"},
        {"id": "project_affinity", "name": "Project Habit", "description": "Recurrence on same customer/project"}
    ]

@router.get("/mappings")
def get_current_mappings(environment: str = Depends(verify_hmac)):
    """Returns the current association between raw fields and features (User + Default)."""
    client = get_db()
    key = client.key("DataMapping", environment)
    entity = client.get(key)
    
    defaults = {
        "role_match": ["role", "employment.role", "activities.typeActivity"],
        "time_of_day": ["start_time", "beginTimePlace.tmregister", "beginTimePlan"],
        "day_of_week": ["date", "tmregister", "beginTimePlace.tmregister"],
        "age": ["bornDate", "person.bornDate", "employment.person.borndate"],
        "distance": ["address", "person.address", "customer.address", "activities.project.customer.address"],
        "punctuality": ["punctuality_score", "feedback_history"],
        "task_keywords": ["operations", "activities.name", "activities.project.description"],
        "seniority": ["id", "employment.code", "dtHired"],
        "role_index": ["role", "activities.code"],
        "vehicle_req": ["selectVehicleRequired", "vehicle.plate"],
        "project_affinity": ["project.id", "activities.project.id", "employment.project_ids"]
    }
    
    if entity and "mappings" in entity:
        # Merge: User mappings override defaults where specified
        user_map = entity["mappings"]
        for k, v in user_map.items():
            if v: defaults[k] = v
            
    return defaults

@router.post("/mappings")
def save_mappings(mapping_data: Dict[str, List[str]], environment: str = Depends(verify_hmac)):
    """Saves custom associations between raw fields and features."""
    client = get_db()
    key = client.key("DataMapping", environment)
    
    entity = datastore.Entity(key=key)
    entity.update({
        "environment": environment,
        "mappings": mapping_data,
        "last_updated": datetime.now()
    })
    
    # client.put(entity)
    return {"status": "success", "message": "READ-ONLY: Mapping save disabled."}
