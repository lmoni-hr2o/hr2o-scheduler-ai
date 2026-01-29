from fastapi import APIRouter, HTTPException, Depends
# from firebase_admin import firestore  # Replaced with Datastore
from utils.datastore_helper import get_db
from pydantic import BaseModel
from typing import List, Optional
from solver.engine import solve_schedule
from scorer.model import NeuralScorer
from utils.security import verify_hmac

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
    employees: List[Employee]
    required_shifts: Optional[List[ShiftRequirement]] = []
    unavailabilities: Optional[List[Unavailability]] = []
    activities: Optional[List[dict]] = []
    constraints: Optional[dict] = {}

@router.post("/generate")
def generate_schedule(req: GenerateRequest, environment: str = Depends(verify_hmac)):
    """
    Stateless generation: receives all data, returns the solution.
    Now secured with HMAC and Environment header.
    """
    # 0. Safety Check: Block if training is in progress (avoids race conditions/garbage output)
    from utils.status_manager import get_status, set_running
    status = get_status()
    if status.get("status") == "running":
        # Check staleness (if last update > 5 mins ago, auto-unlock)
        import datetime
        last_upd = status.get("last_updated")
        is_stale = False
        if last_upd:
             # Ensure last_upd is datetime
             if not isinstance(last_upd, datetime.datetime):
                 from utils.date_utils import parse_date
                 last_upd = parse_date(str(last_upd))
             
             if last_upd:
                 diff = datetime.datetime.now(last_upd.tzinfo) - last_upd
                 if diff.total_seconds() > 300: # 5 minutes
                     print(f"WARNING: Stale running status detected ({diff.total_seconds()}s). Auto-unlocking.")
                     is_stale = True

        if not is_stale:
            raise HTTPException(
                status_code=503, 
                detail="System is currently training the AI Brain. Please wait 30 seconds and try again."
            )
        else:
            set_running(False) # Force unlock

    # 1. Prepare data for the solver
    employees_data = [
        {
            "id": emp.id, 
            "name": emp.name, 
            "fullName": emp.name, # Fix for solver logging expecting fullName
            "role": emp.role, 
            "preferences": emp.preferences,
            "project_ids": emp.project_ids,
            "customer_keywords": emp.customer_keywords,
            "address": emp.address,
            "bornDate": emp.bornDate,
            "labor_profile_id": emp.labor_profile_id
        }
        for emp in req.employees
    ]
    
    required_shifts_data = [s.dict() for s in req.required_shifts]
    unavailabilities_data = [u.dict() for u in req.unavailabilities]

    # 2. Optimization
    # Pass 'environment' to the solver for configuration lookup
    result = solve_schedule(
        employees_data, 
        required_shifts_data,
        unavailabilities_data,
        req.constraints, 
        req.start_date, 
        req.end_date,
        activities=req.activities,
        environment=environment
    )

    if result is None:
        raise HTTPException(status_code=400, detail="Infeasible schedule: could not find a valid solution with these constraints.")

    # 3. Return the solution directly
    return {
        "status": "success",
        "solver_status": "optimal",
        "schedule": result
    }

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
                act_name = get_nested(p, ["activities.name", "activity_name", "activities.project.description"], "Fixed Activity")

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
