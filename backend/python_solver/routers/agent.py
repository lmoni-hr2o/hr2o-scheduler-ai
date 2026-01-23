from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict
from datetime import datetime
import requests
from google.cloud import datastore
from models import Activity, Employment, Period, DataMapping
from utils.security import verify_hmac
import firebase_admin
# from firebase_admin import firestore  # Replaced with Datastore
from utils.datastore_helper import get_db
from utils.mapping_helper import mapper

router = APIRouter(prefix="/agent", tags=["Agent"])

# Host API Configuration - 
EXTERNAL_ACTIVITY_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/activity?namespace=OVERCLEAN"
EXTERNAL_EMPLOYMENT_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/employment?namespace=OVERCLEAN"
EXTERNAL_PERIOD_URL = "https://europe-west3-hrtimeplace.cloudfunctions.net/period?namespace=OVERCLEAN&isplan=true&iscalc=false&start=01022023&end=02022023"

@router.get("/ping")
def ping():
    return {"status": "Agent Router is reachable"}

@router.get("/companies")
def get_companies(environment: str = Depends(verify_hmac)):
    """Fetches high-quality client companies (those with activities and historical periods)."""
    try:
        # Use mapper to get only companies that have real data to work with
        active_companies = mapper.get_all_companies()
        print(f"DEBUG: Mapper returned {len(active_companies)} active companies for {environment}")
        return active_companies
    except Exception as e:
        print(f"ERROR filtering companies: {e}")
        # Return empty list or raise error
        return []

@router.get("/activities", response_model=List[Activity])
def get_activities(environment: str = Depends(verify_hmac)):
    """Fetches activity data using the mapper's pre-warmed cache."""
    print(f"DEBUG: Fetching activities for environment: {environment} (cached)")
    try:
        raw_list = mapper.get_activities(environment)
        print(f"DEBUG: Mapper returned {len(raw_list)} activities for {environment}")
        print(f"DEBUG: Mapper entities keys: {list(mapper._entities.keys())}")
        activities_dict = {}
        for data in raw_list:
            activity_data = data.get("activities")
            if not activity_data and ("name" in data or "project" in data):
                activity_data = data
            
            if activity_data and isinstance(activity_data, dict):
                # ID can be in _entity_id (Datastore key), activity.id, or top-level id
                act_id = (
                    str(data.get("_entity_id", "")) or
                    str(activity_data.get("id", "")) or 
                    str(data.get("id", ""))
                )
                if act_id and act_id not in activities_dict:
                    # Convert datetime to ISO string
                    dt_end = activity_data.get("dtEnd")
                    if dt_end and hasattr(dt_end, 'isoformat'):
                        dt_end = dt_end.isoformat()
                    
                    activities_dict[act_id] = Activity(
                        id=act_id,
                        name=activity_data.get("name", "Unknown Activity"),
                        role_required="worker",
                        environment=environment,
                        project=activity_data.get("project"),
                        customer_address=activity_data.get("project", {}).get("customer", {}).get("address") if activity_data.get("project") else None,
                        code=activity_data.get("code"),
                        note=activity_data.get("note"),
                        typeActivity=activity_data.get("typeActivity"),
                        dtEnd=dt_end,
                        type=activity_data.get("type"),
                        productivityType=activity_data.get("productivityType"),
                        operations=activity_data.get("operations"),
                        selectVehicleRequired=activity_data.get("selectVehicleRequired", False)
                    )
        return list(activities_dict.values())
    except Exception as e:
        print(f"ERROR in cached activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/employment", response_model=List[Employment])
def get_employment(environment: str = Depends(verify_hmac)):
    """Fetches employment data using the mapper's pre-warmed cache."""
    print(f"DEBUG: Fetching employment for environment: {environment} (cached)")
    try:
        raw_list = mapper.get_employment(environment)
        raw_periods = mapper.get_periods(environment)
        
        # 1. PRE-PROCESS HISTORY (Single Pass)
        ids_with_history = set()
        history_map = {} # emp_id -> {project_ids: set, keywords: set}
        
        for p in raw_periods:
            emp_sub = p.get("employment", {})
            # Link via multiple possible IDs
            p_ids = set()
            p_id = str(emp_sub.get("id", "")) if isinstance(emp_sub, dict) else str(emp_sub or "")
            if p_id: p_ids.add(p_id)
            if p.get("_entity_id"): p_ids.add(str(p.get("_entity_id")))
            p_ext = str(p.get("employmentId", "")) or str(p.get("employee_id", ""))
            if p_ext: p_ids.add(p_ext)
            badge = (emp_sub or {}).get("badge") if isinstance(emp_sub, dict) else None
            if badge: p_ids.add(str(badge))

            # Store for "has_history" badge
            for pid in p_ids:
                if pid and pid.lower() not in ["none", "", "null"]:
                    ids_with_history.add(pid)

            # Build detailed history map for Neural Affinity
            target_emp_id = p_id or p_ext
            if target_emp_id:
                if target_emp_id not in history_map:
                    history_map[target_emp_id] = {"project_ids": set(), "keywords": set()}
                
                act = p.get("activities", {})
                proj = act.get("project", {})
                if proj:
                    proj_id = str(proj.get("id") or "")
                    if proj_id: history_map[target_emp_id]["project_ids"].add(proj_id)
                    cust = proj.get("customer", {})
                    for k in ["name", "address"]:
                        val = cust.get(k, "")
                        if val: history_map[target_emp_id]["keywords"].add(str(val).upper()[:5])

        # 2. PROCESS EMPLOYEES
        employees_dict = {}
        processed_keys = {} # name_born -> emp_id
        
        for i, data in enumerate(raw_list):
            employment_data = data.get("employment") if "employment" in data else data
            if not isinstance(employment_data, dict): continue
                
            comp_data = employment_data.get("company") or data.get("employment.company") or {}
            person_data = employment_data.get("person") or data.get("employment.person") or {}
            if not isinstance(comp_data, dict): comp_data = {}
            if not isinstance(person_data, dict): person_data = {}
            
            # Canonical ID resolution
            real_id = str(employment_data.get("id", "")) or str(data.get("id", ""))
            entity_id = str(data.get("_entity_id", ""))
            emp_id = real_id if real_id and real_id.lower() not in ["none", "null", ""] else entity_id
            
            if not emp_id: continue
            
            full_name = person_data.get("fullName", "").strip() or person_data.get("name", "").strip() or f"Worker {i}"
            born_date_raw = person_data.get("bornDate")
            born_date_str = born_date_raw.isoformat() if hasattr(born_date_raw, 'isoformat') else str(born_date_raw)
            
            # Deduplication
            dedup_key = f"{full_name.lower()}_{born_date_str}" if full_name != f"Worker {i}" else emp_id
            if dedup_key in processed_keys: continue
            
            # Termination Check
            dt_dismissed = employment_data.get("dtDismissed")
            if dt_dismissed and hasattr(dt_dismissed, 'isoformat'): dt_dismissed = dt_dismissed.isoformat()
            if dt_dismissed:
                try:
                    d_date = datetime.fromisoformat(dt_dismissed.split('T')[0])
                    if d_date < datetime.now(): continue
                except: pass

            processed_keys[dedup_key] = emp_id

            # History Linking
            h_data = history_map.get(emp_id, history_map.get(real_id, {"project_ids": set(), "keywords": set()}))
            emp_has_history = (emp_id in ids_with_history) or (real_id in ids_with_history) or (entity_id in ids_with_history)
            badge_val = str(employment_data.get("badge", ""))
            if badge_val and badge_val in ids_with_history: emp_has_history = True

            employees_dict[emp_id] = Employment(
                id=emp_id,
                name=comp_data.get("name", environment),
                fullName=full_name,
                role=str(employment_data.get("role", "worker")).lower(),
                environment=environment,
                company=comp_data,
                person=person_data,
                address=person_data.get("address"),
                city=person_data.get("city"),
                bornDate=born_date_str,
                dtHired=str(employment_data.get("dtHired", "")),
                dtDismissed=dt_dismissed,
                has_history=emp_has_history,
                badge=employment_data.get("badge"),
                project_ids=list(h_data["project_ids"]),
                customer_keywords=list(h_data["keywords"])
            )
        
        return list(employees_dict.values())
    except Exception as e:
        print(f"ERROR in cached employment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/periods", response_model=List[Period])
def get_periods(
    start_date: datetime, 
    end_date: datetime, 
    environment: str = Depends(verify_hmac)
):
    """
    Legge i Periodi dall'API esterna dell'host.
    """
    if "URL_PERIOD" in EXTERNAL_PERIOD_URL or "INSERISCI_QUI" in EXTERNAL_PERIOD_URL:
        try:
            from utils.datastore_helper import get_db
            db = get_db()
            # Match Firestore structure to Datastore logic
            docs = db.collection("environments").document(environment).collection("periods") \
                    .where("tmregister", ">=", start_date) \
                    .where("tmregister", "<=", end_date) \
                    .stream()
            return [Period(**doc.to_dict()) for doc in docs]
        except Exception as e:
            print(f"DEBUG: Internal periods fetch failed: {e}")
            return []

    try:
        params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
        response = requests.get(EXTERNAL_PERIOD_URL, params=params, headers={"Environment": environment})
        response.raise_for_status()
        data = response.json()
        return [Period(**item) for item in data] if isinstance(data, list) else []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Host Period (Read) API Error: {str(e)}")

@router.post("/periods", response_model=Period)
def create_period(period: Period, environment: str = Depends(verify_hmac)):
    """
    Scrive un Periodo nell'API esterna dell'host.
    """
    if period.environment != environment:
        raise HTTPException(status_code=400, detail="Environment mismatch between body and header.")
    
    if "URL_PERIOD" in EXTERNAL_PERIOD_URL or "INSERISCI_QUI" in EXTERNAL_PERIOD_URL:
        try:
            from utils.datastore_helper import get_db
            db = get_db()
            doc_ref = db.collection("environments").document(environment).collection("periods").document()
            period_dict = period.dict()
            period_dict["id"] = doc_ref.id
            doc_ref.set(period_dict)
            return Period(**period_dict)
        except Exception as e:
            print(f"DEBUG: Internal period creation failed: {e}")
            return period

    try:
        response = requests.post(EXTERNAL_PERIOD_URL, json=period.dict(), headers={"Environment": environment})
        response.raise_for_status()
        return Period(**response.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Host Period (Write) API Error: {str(e)}")

@router.get("/diagnostics")
def get_diagnostics(environment: str = Depends(verify_hmac)):
    """Exposes data quality metrics for the current company."""
    return mapper.get_diagnostics(environment)

@router.post("/reset_status")
def reset_status():
    """Force reset system status to idle/complete."""
    from utils.status_manager import set_running
    set_running(False)
    return {"status": "System status reset to IDLE"}

@router.get("/data-map")
def get_data_map():
    """Returns a summary of all companies and their entity counts."""
    mapper.refresh_if_needed()
    res = []
    for cid, data in mapper._entities.items():
        if not isinstance(data, dict): continue
        
        pers = data.get("Period", [])
        
        def get_nested_local(obj, key_variants, default=None):
            for kv in key_variants:
                if kv in obj: return obj[kv]
                parts = kv.split('.')
                curr = obj
                for p_part in parts:
                    if isinstance(curr, dict) and p_part in curr:
                        curr = curr[p_part]
                    else:
                        curr = None
                        break
                if curr is not None: return curr
            return default

        # Get date range and samples
        min_date, max_date = "N/A", "N/A"
        samples = []
        p_keys = []
        if pers:
            p_keys = list(pers[0].keys())
            try:
                dates = []
                from utils.date_utils import parse_date
                for p in pers:
                    raw_val = get_nested_local(p, ["tmregister", "tmRegister", "beginTimePlace.tmregister", "date"])
                    if raw_val and len(samples) < 5: samples.append(f"{str(raw_val)} ({type(raw_val).__name__})")
                    d = parse_date(raw_val)
                    if d: dates.append(d)
                if dates:
                    min_date = min(dates).strftime("%Y-%m")
                    max_date = max(dates).strftime("%Y-%m")
            except: pass

        res.append({
            "id": cid,
            "name": mapper._mappings.get(cid, {}).get("name", cid),
            "Activities": len(data.get("Activity", [])),
            "Employments": len(data.get("Employment", [])),
            "Periods": len(pers),
            "Keys": p_keys,
            "Quality": mapper._diagnostics.get(cid, {}).get("quality_score", 0),
            "Range": f"{min_date} to {max_date}",
            "DateSamples": samples
        })
    
    # Sort by companies with most periods
    res.sort(key=lambda x: x['Periods'], reverse=True)
    return res[:20]

@router.get("/schema")
def get_company_schema(environment: str = Depends(verify_hmac)):
    """Discovers all available fields in the company data entities."""
    mapper.refresh_if_needed()
    
    # Use environment as company_id (standard in our headers)
    company_id = environment
    
    entities = mapper._entities.get(company_id, {})
    if not entities:
        # Try finding by name/alias just in case
        for cid, info in mapper._mappings.items():
            if company_id in info.get("aliases", []) or company_id == info["name"]:
                entities = mapper._entities.get(cid, {})
                break

    res = {
        "Employment": [],
        "Activity": [],
        "Period": []
    }

    def flatten_keys(d, prefix=""):
        keys = []
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    keys.extend(flatten_keys(v, f"{prefix}{k}."))
                else:
                    keys.append(f"{prefix}{k}")
        elif isinstance(d, list) and d:
             # Sample from list
             keys.extend(flatten_keys(d[0], prefix))
        return keys

    for kind in res.keys():
        samples = entities.get(kind, [])
        if samples:
            # Aggregate keys from up to 5 samples to be sure
            all_keys = set()
            for s in samples[:5]:
                all_keys.update(flatten_keys(s))
            res[kind] = sorted(list(all_keys))
            
    return res

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
    
    client.put(entity)
    return {"status": "success", "message": "Data mappings saved."}
