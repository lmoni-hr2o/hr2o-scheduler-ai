from fastapi import APIRouter, HTTPException, Request
from utils.datastore_helper import get_db
from solver.engine import solve_schedule
from pydantic import BaseModel
from typing import List, Optional
import traceback
import json
import datetime
from utils.payload_handler import compress_payload, decompress_payload

router = APIRouter(prefix="/worker", tags=["Worker"])

class WorkerPayload(BaseModel):
    job_id: str

@router.post("/solve")
def solve_worker(payload: WorkerPayload):
    """
    Background worker that solves the schedule.
    Triggered by Cloud Tasks.
    """
    job_id = payload.job_id
    print(f"WORKER: Starting processing for Job ID: {job_id}")

    import psutil, os
    proc = psutil.Process(os.getpid())
    def log_mem(label):
        mem = proc.memory_info().rss / (1024 * 1024)
        print(f"DIAGNOSTIC [Worker]: {label} | Memory: {mem:.1f} MB")

    log_mem("Worker starting job")

    client = get_db().client
    key = client.key("AsyncJob", job_id)
    job = client.get(key)

    if not job:
        print(f"CRITICAL: Job {job_id} not found.")
        return {"status": "error", "message": "Job not found"}

    # Update status to processing
    environment = job.get("environment")
    key = client.key("AsyncJob", job_id, namespace=environment)
    job = client.get(key) # Refresh with namespace
    
    if not job:
        print(f"CRITICAL: Job {job_id} not found in namespace {environment}")
        return {"status": "error"}

    job["status"] = "processing"
    job["updated_at"] = datetime.datetime.now()
    # client.put(job)

    try:
        req_data = {}
        if "request_payload" in job:
             req_data = json.loads(decompress_payload(job["request_payload"]))
        else:
            req_data = job

        employees = req_data.get("employees", [])
        activities = req_data.get("activities", [])

        # 1. Fetch Employees if missing
        if not employees:
            print(f"WORKER: Pulling employees from Datastore for {environment}...")
            MAX_ITEMS_WORKER = 2000 
            db_env = get_db(namespace=environment).client
            query = db_env.query(kind="Employment")
            employees = []
            for entity in query.fetch(limit=MAX_ITEMS_WORKER):
                emp = dict(entity)
                emp["id"] = entity.key.name
                employees.append({
                     "id": emp.get("id"), 
                     "name": emp.get("name"), 
                     "fullName": emp.get("fullName") or emp.get("name"), 
                     "role": emp.get("role"), 
                })
        
        # 2. Fetch Activities if missing
        if not activities:
            print(f"WORKER: Pulling activities from Datastore for {environment}...")
            MAX_ITEMS_WORKER = 2000
            db_env = get_db(namespace=environment).client
            query = db_env.query(kind="Activity")
            activities = []
            for entity in query.fetch(limit=MAX_ITEMS_WORKER):
                act = dict(entity)
                act["id"] = entity.key.name
                activities.append(act)

        # 3. Setup other data
        required_shifts = req_data.get("required_shifts", [])
        unavailabilities = req_data.get("unavailabilities", [])

        # 4. SOLVE
        print(f"WORKER: Solving for Job {job_id}")
        
        result = solve_schedule(
            employees=employees, 
            required_shifts=required_shifts,
            unavailabilities=unavailabilities,
            constraints=req_data.get("constraints", {}), 
            start_date_str=req_data.get("start_date"), 
            end_date_str=req_data.get("end_date"),
            activities=activities,
            environment=environment
        )

        # 5. Result Handling: Save back to Datastore
        job["status"] = "completed"
        job["result"] = compress_payload(json.dumps(result))
        job["updated_at"] = datetime.datetime.now()
        # # client.put(job)
        print(f"WORKER: [Read-Only] Job {job_id} Completed (No Save).")

    except Exception as e:
        print(f"WORKER CRITICAL Error: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["updated_at"] = datetime.datetime.now()
        # client.put(job)
        traceback.print_exc()
    
    return {"status": "ok"}
