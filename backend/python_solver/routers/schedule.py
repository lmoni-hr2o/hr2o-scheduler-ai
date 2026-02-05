from fastapi import APIRouter, HTTPException, Depends
# from firebase_admin import firestore  # Replaced with Datastore
from utils.datastore_helper import get_db
from pydantic import BaseModel
from typing import List, Optional
from solver.engine import solve_schedule
from scorer.model import NeuralScorer
from utils.security import verify_hmac
import uuid
import datetime
import json
from utils.cloud_tasks import enqueue_task

router = APIRouter(prefix="/schedule", tags=["Schedule"])

class Employee(BaseModel):
    id: str
    name: str
    role: str
    preferences: Optional[List[float]] = [0.5, 0.5]
    project_ids: Optional[List[str]] = []
    customer_keywords: Optional[List[str]] = []
    address: Optional[str] = None
    bornDate: Optional[str] = None
    labor_profile_id: Optional[str] = None
    fullName: Optional[str] = None

class ShiftRequirement(BaseModel):
    id: str
    date: str # ISO string "YYYY-MM-DD"
    start_time: str # "HH:mm"
    end_time: str # "HH:mm"
    role: str
    project: Optional[dict] = None

class Unavailability(BaseModel):
    employee_id: str
    date: str
    start_time: Optional[str] = None # None means all day
    end_time: Optional[str] = None

class GenerateRequest(BaseModel):
    start_date: str
    end_date: str
    employees: List[dict] # Bypassing Pydantic model for memory efficiency
    required_shifts: Optional[List[dict]] = []
    unavailabilities: Optional[List[dict]] = []
    activities: Optional[List[dict]] = []
    constraints: Optional[dict] = {}

@router.post("/generate")
def generate_schedule(req: GenerateRequest, environment: str = Depends(verify_hmac)):
    """
    Async generation: Saves request, enqueues Cloud Task, returns job_id.
    """
    try:
        job_id = str(uuid.uuid4())
        print(f"DEBUG: Enqueuing Async Job {job_id} for env {environment}")

        # 1. Save Request to Datastore
        client = get_db().client
        key = client.key("AsyncJob", job_id)
        job = {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "environment": environment,
            # We store the raw request as a dict
            "request_payload": json.dumps(req.dict()) 
        }
        entity = client.entity(key=key, exclude_from_indexes=["request_payload"])
        entity.update(job)
        client.put(entity)

        # 2. Enqueue Task
        # Payload for worker just needs ID
        task_name = enqueue_task("/worker/solve", {"job_id": job_id})
        
        # 3. Return Job ID
        return {
            "status": "queued",
            "job_id": job_id,
            "task_name": task_name,
            "message": "Schedule generation started in background."
        }

    except Exception as e:
        import traceback
        print(f"CRITICAL: Error enqueuing job: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}")
def get_job_status(job_id: str):
    """
    Polls the status of an async job.
    """
    try:
        client = get_db().client
        key = client.key("AsyncJob", job_id)
        job = client.get(key)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        status = job.get("status", "unknown")
        
        response = {
            "job_id": job_id,
            "status": status,
            "updated_at": str(job.get("updated_at"))
        }

        if status == "completed":
             # Parse result
             import json
             try:
                 # Check if result is stored as string or blob
                 res = job.get("result", "{}")
                 if isinstance(res, bytes):
                     res = res.decode('utf-8')
                 response["schedule"] = json.loads(res)
                 response["solver_status"] = "optimal" # Fallback/Assume
             except Exception as e:
                 print(f"Error parsing result: {e}")
                 response["schedule"] = []
                 response["error"] = "Failed to parse result"
        
        elif status == "failed":
            response["error"] = job.get("error", "Unknown error")
            response["traceback"] = job.get("traceback")

        return response

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical")
def get_historical_schedule(start_date: str, end_date: str, environment: str = Depends(verify_hmac)):
    """Fetches historical shift data (Period) for the given range and environment."""
    # from utils.mapping_helper import mapper # Removed
    from utils.date_utils import parse_date, format_date_iso
    
    # Direct Datastore Query
    client = get_db(namespace=environment).client
    raw_periods = []
    try:
        query = client.query(kind="Period")
        # Optimization: Filter by date if possible, but Period structure varies.
        # Ideally: .add_filter("tmregister", ">=", start_date)
        # For now, fetch all (or limit) and filter updates to keep logic identical to legacy
        # But for 'History' we probably want a limit
        # raw_periods = list(query.fetch(limit=2000))
        # Better: Filter by range if we can trust the 'tmregister' field is indexed
        # Let's try basic fetch and filter in memory to be safe as per legacy behavior
        for entity in query.fetch(limit=5000):
            p = dict(entity)
            p["_entity_id"] = entity.key.name
            raw_periods.append(p)
    except Exception as e:
        print(f"Error querying periods: {e}")

    
    # Parse range dates
    try:
        range_start = parse_date(start_date)
        range_end = parse_date(end_date)
    except:
        raise HTTPException(status_code=400, detail="Invalid date format for filter")

    historical_shifts = []
    for p in raw_periods:
        try:
            # Dotted key lookup helper for flat-nested structures
            def get_nested(obj, key_variants, default=None):
                for kv in key_variants:
                    # Try direct dotted lookup (flat)
                    if kv in obj: return obj[kv]
                    # Try nested lookup
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

            # Extract Register Date
            tm_raw = get_nested(p, ["tmregister", "tmRegister", "beginTimePlace.tmregister", "date"])
            reg_dt = parse_date(tm_raw)
            
            if reg_dt and range_start <= reg_dt <= range_end:
                tmentry = get_nested(p, ["tmentry", "beginTimePlace.tmregister", "beginTimePlan"])
                tmexit = get_nested(p, ["tmexit", "endTimePlace.tmregister", "endTimePlan"])
                
                def format_time(t):
                    if hasattr(t, 'strftime'): return t.strftime("%H:%M")
                    pts = parse_date(t)
                    if pts: return pts.strftime("%H:%M")
                    # Fallback string split
                    ts = str(t).split('T')[-1].split(':')
                    if len(ts) >= 2: return f"{ts[0]:02}:{ts[1]:02}"
                    return "00:00"

                # Employee ID and Name
                emp_data = p.get("employment", {})
                emp_id = get_nested(p, ["employment.id", "employmentId", "employee_id", "employment.code"])
                if not emp_id and isinstance(emp_data, dict):
                    emp_id = emp_data.get("id") or emp_data.get("code")

                emp_name = get_nested(p, ["employment.person.fullName", "employee_name", "employment.fullName"], "Unknown Worker")
                
                # Activity Name
                # Handle list of activities (common case) or dict
                acts = p.get("activities")
                if isinstance(acts, list) and len(acts) > 0:
                    first_act = acts[0]
                    # Try name, or project description, or code
                    act_name = first_act.get("name") or first_act.get("project", {}).get("description") or first_act.get("code") or "Unknown Task"
                elif isinstance(acts, dict):
                     act_name = acts.get("name") or acts.get("project", {}).get("description") or "Unknown Task"
                else:
                    act_name = get_nested(p, ["activity_name", "activities.name"], "N/A")

                historical_shifts.append({
                    "id": str(p.get("_entity_id", "") or p.get("id", "") or "P" + str(len(historical_shifts))),
                    "date": format_date_iso(reg_dt),
                    "employee_id": str(emp_id),
                    "employee_name": str(emp_name),
                    "activity_name": str(act_name),
                    "start_time": format_time(tmentry),
                    "end_time": format_time(tmexit),
                    "is_historical": True
                })
        except Exception as e:
            print(f"DEBUG: Error processing historical period: {e}")
            continue
        
    return historical_shifts
