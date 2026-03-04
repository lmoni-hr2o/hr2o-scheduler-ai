from fastapi import APIRouter, HTTPException, Depends
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
from utils.payload_handler import compress_payload, decompress_payload

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

class GenerateRequest(BaseModel):
    start_date: str
    end_date: str
    employees: List[dict]
    required_shifts: Optional[List[dict]] = []
    unavailabilities: Optional[List[dict]] = []
    activities: Optional[List[dict]] = []
    constraints: Optional[dict] = {}

from utils.errors import PlannerError
from config import settings

def get_current_db(environment: str = Depends(verify_hmac)):
    db = get_db(namespace=environment)
    return db.client, environment

@router.post("/generate")
def generate_schedule(
    req: GenerateRequest, 
    environment: str = Depends(verify_hmac)
):
    """
    Purely synchronous and stateless generation. 
    Returns results directly without writing to Datastore (Read-Only).
    """
    try:
        print(f"DEBUG: Starting Synchronous Read-Only Solve for env {environment}")
        
        results = solve_schedule(
            employees=req.employees,
            required_shifts=req.required_shifts,
            unavailabilities=req.unavailabilities,
            constraints=req.constraints,
            start_date_str=req.start_date,
            end_date_str=req.end_date,
            activities=req.activities,
            environment=environment
        )
        
        return {
            "status": "completed",
            "job_id": f"sync_{uuid.uuid4().hex[:8]}",
            "schedule": results,
            "message": "Schedule generated successfully (Read-Only Mode)."
        }

    except Exception as e:
        import traceback
        print(f"CRITICAL: Error during solve: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/historical")
def get_historical_schedule(
    start_date: str, 
    end_date: str, 
    min_duration: int = 60,
    environment: str = Depends(verify_hmac)
):
    """
    Fetches historical assignments (Periods) from Datastore.
    Maps them to a simplified shift format for the frontend.
    """
    try:
        from utils.date_utils import parse_date
        sd = parse_date(start_date)
        ed = parse_date(end_date)
        
        if not sd or not ed:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        client = get_db(namespace=environment).client
        query = client.query(kind="Period")
        query.add_filter("tmregister", ">=", sd.isoformat())
        query.add_filter("tmregister", "<=", ed.isoformat())
        
        results = []
        for entity in query.fetch():
            data = dict(entity)
            # Map Datastore Period to UI Shift format
            start_t = data.get("beginTimePlan") or data.get("tmregister")
            end_t = data.get("endTimePlan") or data.get("endTimeCalc") or start_t
            
            if not start_t:
                continue

            # Robust time parsing
            def format_time(t):
                if isinstance(t, str):
                    if "T" in t: return t.split("T")[1][:5]
                    if ":" in t: return t[:5]
                    return "08:00"
                if hasattr(t, "strftime"):
                    return t.strftime("%H:%M")
                return "08:00"

            def format_date(t):
                if isinstance(t, str):
                    if "T" in t: return t.split("T")[0]
                    return t
                if hasattr(t, "strftime"):
                    return t.strftime("%Y-%m-%d")
                return "2026-01-01"

            s_str = format_time(start_t)
            e_str = format_time(end_t)
            d_str = format_date(start_t)

            # Filter out shifts shorter than 60 minutes in historical view too
            try:
                h1, m1 = map(int, s_str.split(':'))
                h2, m2 = map(int, e_str.split(':'))
                dur = (h2 * 60 + m2) - (h1 * 60 + m1)
                if dur < 0: dur += 1440
                if dur < min_duration: continue # Skip short tasks based on config
            except:
                pass

            # Extract activity info
            act_data = data.get("activities") or {}
            role = "worker"
            if isinstance(act_data, dict):
                role = act_data.get("name") or act_data.get("code") or "worker"
            elif isinstance(act_data, list) and act_data:
                role = act_data[0].get("name") or "worker"

            results.append({
                "id": entity.key.name or str(entity.key.id),
                "employee_id": data.get("employmentId") or data.get("employee_id"),
                "date": d_str,
                "start_time": s_str,
                "end_time": e_str,
                "role": role,
                "is_historical": True
            })
            
        return results

    except Exception as e:
        print(f"ERROR fetching historical schedule: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}")
def get_job_status(
    job_id: str, 
    db_ctx: tuple = Depends(get_current_db)
):
    """
    Polls the status of an async job within the environment namespace.
    """
    client, environment = db_ctx
    try:
        key = client.key("AsyncJob", job_id, namespace=environment)
        job = client.get(key)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found. It may have expired or was never created.")
        
        status = job.get("status", "unknown")
        
        response = {
            "job_id": job_id,
            "status": status,
            "updated_at": str(job.get("updated_at"))
        }

        if status == "completed" and "result" in job:
            response["schedule"] = decompress_payload(job["result"])
        elif status == "failed":
            response["error"] = job.get("error", "Unknown error")
            
        return response

    except Exception as e:
        print(f"ERROR polling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
