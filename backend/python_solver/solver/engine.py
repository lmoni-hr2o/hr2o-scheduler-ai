from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import numpy as np
import psutil
import gc
import random
import time

from config import settings
from utils.status_manager import set_running, update_status as _upd
from utils.errors import InfeasibleError, MemoryLimitError
from services.demand_service import DemandService
from services.policy_service import PolicyService
from solver.constraints.factory import ConstraintFactory
from scorer.model import NeuralScorer
from utils.datastore_helper import get_db

def update_status(message=None, progress=None, phase=None, log=None, details=None):
    _upd(message=message, progress=progress, phase=phase, log=log, details=details)

def normalize_name(name):
    if not name: return ""
    import re
    clean = re.sub(r'[^A-Z0-9\s]', '', name.upper())
    words = sorted(clean.split())
    return " ".join(words)

def solve_schedule(employees: list, required_shifts: list, unavailabilities: list, constraints: dict, 
                   start_date_str: str, end_date_str: str, activities: list = [], environment: str = "default"):
    set_running(True)
    
    try:
        # 1. Deduplication (Priority to ID)
        unique_employees = []
        id_dedupe, seen_names = set(), set()
        for emp in employees:
            eid = str(emp.get("id") or emp.get("employee_id") or "").strip()
            fname = normalize_name(emp.get("fullName") or emp.get("name") or "")
            if eid:
                if eid in id_dedupe: continue
                id_dedupe.add(eid)
                if fname: seen_names.add(fname)
            elif fname:
                if fname in seen_names: continue
                seen_names.add(fname)
            else: continue
            unique_employees.append(emp)
        employees = unique_employees

        # 2. Demand Generation (Service)
        demand_service = DemandService(environment)
        if not required_shifts:
            update_status(message="Generating Demand...", progress=0.1)
            required_shifts = demand_service.generate_shifts(start_date_str, end_date_str, activities)
        
        if not required_shifts:
            update_status(message="No shifts to solve", progress=1.0)
            return []

        # 3. Model Initialization
        model = cp_model.CpModel()
        x = {} # (e_idx, s_idx) -> BoolVar
        unassigned = {s_idx: model.NewBoolVar(f'unassigned_{s_idx}') for s_idx in range(len(required_shifts))}
        
        # 4. Neural Affinities & Sparse Creation
        scorer = NeuralScorer()
        scorer.refresh_if_needed(force=True)
        
        # Load environment-specific config
        client = get_db().client
        key = client.key("AlgorithmConfig", environment)
        db_config = client.get(key) or {}
        
        aff_weight = constraints.get("affinity_weight", db_config.get("affinity_weight", settings.AFFINITY_WEIGHT))
        fair_weight = constraints.get("fairness_weight", db_config.get("fairness_weight", settings.FAIRNESS_WEIGHT))
        
        # Viability & Variable Creation
        update_status(message="Analyzing Viability...", progress=0.2)
        all_features, pairs = [], []
        for e_idx, emp in enumerate(employees):
            for s_idx, shift in enumerate(required_shifts):
                # Simple role match ( जंगलीWildcard logic)
                e_role, s_role = str(emp.get("role","")).upper(), str(shift.get("role","")).upper()
                if e_role == s_role or e_role == "WORKER" or s_role == "WORKER":
                    x[(e_idx, s_idx)] = model.NewBoolVar(f'x_{e_idx}_{s_idx}')
                    pairs.append((e_idx, s_idx))
                    all_features.append(scorer.extract_features(emp, shift))

        # Batch Inference
        affinity_map = {}
        if all_features and scorer.enabled:
            update_status(message="Neural Scoring...", progress=0.3)
            preds = scorer.predict_batch(np.array(all_features))
            for idx, (e_idx, s_idx) in enumerate(pairs):
                affinity_map[(e_idx, s_idx)] = int(preds[idx][0] * 100)
            del all_features, preds; gc.collect()

        # 5. Pre-calculate details for constraints
        base_date = datetime.fromisoformat(required_shifts[0]["date"])
        shift_details = []
        shift_durations = []
        for s in required_shifts:
            h1, m1 = map(int, s["start_time"].split(':'))
            h2, m2 = map(int, s["end_time"].split(':'))
            dur = (h2*60 + m2) - (h1*60 + m1)
            if dur < 0: dur += 1440
            d_obj = datetime.fromisoformat(s["date"])
            offset = (d_obj - base_date).days
            shift_details.append((h1*60+m1, h2*60+m2, d_obj, offset*1440 + h1*60+m1, offset*1440 + h1*60+m1 + dur))
            shift_durations.append(dur)

        emp_shifts_by_day = {e_idx: {} for e_idx in range(len(employees))}
        for (e_idx, s_idx) in x.keys():
            day_offset = shift_details[s_idx][3] // 1440
            if day_offset not in emp_shifts_by_day[e_idx]: emp_shifts_by_day[e_idx][day_offset] = []
            emp_shifts_by_day[e_idx][day_offset].append(s_idx)

        # 6. Apply Constraints (Pluggable)
        update_status(message="Applying Constraints...", progress=0.5)
        # Load profiles for PolicyService
        labor_profiles = {} # To be populated from Datastore as before
        policy_service = PolicyService(labor_profiles)
        
        context = {
            'x': x, 'unassigned': unassigned, 'employees': employees, 'required_shifts': required_shifts,
            'shift_details': shift_details, 'shift_durations': shift_durations, 
            'emp_shifts_by_day': emp_shifts_by_day, 'policy_service': policy_service,
            'obj_expr': []
        }
        
        ConstraintFactory().apply_all(model, context)
        obj_expr = context['obj_expr']

        # 7. Final Objective Function
        SCALE = settings.SCALE_FACTOR
        for s_idx in range(len(required_shifts)):
            obj_expr.append(unassigned[s_idx] * -settings.PENALTY_UNASSIGNED * SCALE)
            for e_idx in range(len(employees)):
                if (e_idx, s_idx) in x:
                    aff = affinity_map.get((e_idx, s_idx), 50)
                    jitter = random.randint(0, 30)
                    coeff = (int(aff * aff_weight * SCALE) + int(settings.PENALTY_UNASSIGNED * SCALE)) + jitter
                    obj_expr.append(x[(e_idx, s_idx)] * coeff)

        model.Maximize(cp_model.LinearExpr.Sum(obj_expr))

        # 8. Solve
        update_status(message="Solving...", progress=0.8)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = settings.SOLVE_TIMEOUT_SECONDS
        status = solver.Solve(model)

        if status == cp_model.INFEASIBLE:
            raise InfeasibleError("No valid solution found with current constraints", detail=solver.ResponseStats())

        # 9. Results Processing
        update_status(message="Finalizing Results...", progress=0.9)
        results = []
        has_solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        for s_idx, shift in enumerate(required_shifts):
            assigned = False
            if has_solution:
                for e_idx in range(len(employees)):
                    if (e_idx, s_idx) in x and solver.Value(x[(e_idx, s_idx)]):
                        results.append({
                            **shift, "employee_id": str(employees[e_idx].get("id") or ""),
                            "employee_name": employees[e_idx].get("fullName"),
                            "is_unassigned": False, "affinity": affinity_map.get((e_idx, s_idx), 0) / 100.0
                        })
                        assigned = True; break
            if not assigned:
                results.append({**shift, "employee_id": "unassigned", "employee_name": "Unassigned", "is_unassigned": True})

        update_status(message="Success", progress=1.0)
        return results

    finally:
        set_running(False)
