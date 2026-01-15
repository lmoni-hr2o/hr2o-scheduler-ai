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

class ShiftRequirement(BaseModel):
    id: str
    date: str # ISO string "YYYY-MM-DD"
    start_time: str # "HH:mm"
    end_time: str # "HH:mm"
    role: str

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
    constraints: Optional[dict] = {}

@router.post("/generate")
def generate_schedule(req: GenerateRequest, environment: str = Depends(verify_hmac)):
    """
    Stateless generation: receives all data, returns the solution.
    Now secured with HMAC and Environment header.
    """
    # 1. Prepare data for the solver
    employees_data = [
        {"id": emp.id, "name": emp.name, "role": emp.role, "preferences": emp.preferences}
        for emp in req.employees
    ]
    
    required_shifts_data = [s.dict() for s in req.required_shifts]
    unavailabilities_data = [u.dict() for u in req.unavailabilities]

    # 2. Optimization
    # We can pass 'environment' to the solver if we want to use environment-specific weights
    result = solve_schedule(
        employees_data, 
        required_shifts_data,
        unavailabilities_data,
        req.constraints, 
        req.start_date, 
        req.end_date
    )

    if result is None:
        raise HTTPException(status_code=400, detail="Infeasible schedule: could not find a valid solution with these constraints.")

    # 3. Return the solution directly
    return {
        "status": "success",
        "solver_status": "optimal",
        "schedule": result
    }
