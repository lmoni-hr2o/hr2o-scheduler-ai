from fastapi import APIRouter, HTTPException, Request
from utils.datastore_helper import get_db
from solver.engine import solve_schedule
from pydantic import BaseModel
from typing import List, Optional
import traceback
import json
import datetime

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

    client = get_db().client
    key = client.key("AsyncJob", job_id)
    job = client.get(key)

    if not job:
        print(f"CRITICAL: Job {job_id} not found.")
        return {"status": "error", "message": "Job not found"}

    # Update status to processing
    job["status"] = "processing"
    job["updated_at"] = datetime.datetime.utcnow()
    client.put(job)

    try:
        # Extract payload
        # The payload in Datastore is stored as a blob or large string usually, 
        # but here we'll assume we stored it as structured properties or a JSON string.
        # Let's assume we store the initial request as individual fields in the entity for now,
        # or as a giant 'payload' string if it fits. Given Datastore limits (1MB), large requests might fail.
        # Ideally, large payloads should be in Cloud Storage. 
        # For simplicity in this migration, we'll assume we stored the components in the entity 
        # or as a JSON string 'request_payload'.
        
        req_data = {}
        if "request_payload" in job:
             req_data = json.loads(job["request_payload"])
        else:
            # Fallback for manual inspection/legacy
            req_data = job

        # Reconstruct "GenerateRequest" like object
        employees = req_data.get("employees", [])
        activities = req_data.get("activities", [])
        # Datastore fetch inside worker if needed? 
        # The previous logic allowed "zero-overhead ingestion" where IDs were passed 
        # and the server fetched details. We should support that.
        
        environment = job.get("environment")

        # Reuse the logic from schedule.py (approx)
        # 1. Fetch Employees if missing
        if not employees:
            print(f"WORKER: Pulling employees from Datastore for {environment}...")
            # Limits in worker can be higher
            MAX_ITEMS_WORKER = 2000 
            
            db_env = get_db(namespace=environment).client
            query = db_env.query(kind="Employment")
            employees = []
            count = 0
            for entity in query.fetch(limit=MAX_ITEMS_WORKER):
                emp = dict(entity)
                emp["id"] = entity.key.name
                employees.append({
                     "id": emp.get("id"), 
                     "name": emp.get("name"), 
                     "fullName": emp.get("fullName") or emp.get("name"), 
                     "role": emp.get("role"), 
                     "preferences": emp.get("preferences") or [0.5, 0.5],
                     "project_ids": emp.get("project_ids") or [],
                     "customer_keywords": emp.get("customer_keywords") or [],
                     "address": emp.get("address"),
                     "bornDate": emp.get("bornDate"),
                     "labor_profile_id": emp.get("labor_profile_id"),
                     "dtHired": emp.get("dtHired"),
                     "dtDismissed": emp.get("dtDismissed")
                })
                count += 1
        
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
        required_shifts = []
        for s in req_data.get("required_shifts", []):
             required_shifts.append({
                "id": s.get("id"),
                "date": s.get("date"),
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "role": s.get("role"),
                "activity_id": s.get("activity_id"),
                "project": s.get("project")
            })

        unavailabilities = [
            {
                "employee_id": u.get("employee_id"), 
                "date": u.get("date"), 
                "start_time": u.get("start_time"),
                "end_time": u.get("end_time"),
                "reason": u.get("reason", "Unavailability")
            }
            for u in req_data.get("unavailabilities", [])
        ]

        # 4. SOLVE
        # Note: 'solver.engine.solve_schedule' prints to stdout which goes to logs.
        print(f"WORKER: Solving for {len(employees)} employees, {len(required_shifts)} shifts.")
        
        result = solve_schedule(
            employees, 
            required_shifts,
            unavailabilities,
            req_data.get("constraints", {}), 
            req_data.get("start_date"), 
            req_data.get("end_date"),
            activities=activities,
            environment=environment
        )

        # 5. Save Result
        if result:
            # Check size before saving. Datastore entities < 1MB.
            # Large schedules must be gzipped or stored in a separate list of entities 
            # or Cloud Storage.
            # For this focused task, we try to save to Datastore 'result' property.
            # If it fails, we panic. (Future optimization: Blob storage).
            
            result_json = json.dumps(result)
            if len(result_json.encode('utf-8')) > 900000: # ~900KB safety
                print("WORKER: Warning - Result too large for Datastore. Truncating/Compressing not implemented.")
                # Fallback: Just save empty and maybe log error? 
                # Or save to a separate kind 'ScheduleResult' linked by ID?
                # We'll try to save it as a Blob (bytes) which allows larger sizes (actually 1MB still limit).
                # Text property is 1500 bytes indexed, but unindexed/text is limited by entity size (1MB).
                pass

            # Update Job
            # We exclude from index to allow larger strings
            job.exclude_from_indexes.add("result")
            job["result"] = result_json 
            job["status"] = "completed"
            job["updated_at"] = datetime.datetime.utcnow()
            client.put(job)
            print("WORKER: Job completed successfully.")

        else:
             job["status"] = "failed"
             job["error"] = "Infeasible or No Solution"
             job["updated_at"] = datetime.datetime.utcnow()
             client.put(job)

    except Exception as e:
        print(f"WORKER CRITICAL: {e}")
        traceback.print_exc()
        job["status"] = "failed"
        job["error"] = str(e)
        job["traceback"] = traceback.format_exc()
        job["updated_at"] = datetime.datetime.utcnow()
        client.put(job)
    
    return {"status": "ok"}
