from ortools.sat.python import cp_model
from datetime import datetime, timedelta

def solve_schedule(employees: list, required_shifts: list, unavailabilities: list, constraints: dict, start_date_str: str, end_date_str: str):
    """
    Agentic Solver: Handles variable shift durations, overlap detection, 
    and role-based constraints. 
    Integrates NeuralScorer for soft-constraint optimization.
    """
    from scorer.model import NeuralScorer
    scorer = NeuralScorer()
    
    # Get all unique roles for feature extraction
    all_roles = list(set([s["role"] for s in required_shifts] + [e["role"] for e in employees]))
    
    # --- DIAGNOSTICS ---
    print(f"--- SOLVER STARTING ---")
    print(f"Total Employees: {len(employees)}")
    print(f"Total Shifts: {len(required_shifts)}")
    for r in all_roles:
        emp_count = len([e for e in employees if e["role"] == r])
        shift_count = len([s for s in required_shifts if s["role"] == r])
        print(f"Role '{r}': {emp_count} employees, {shift_count} shifts")
    # -------------------

    model = cp_model.CpModel()
    
    # 1. Default Data Generation (if host system didn't provide specific shifts)
    if not required_shifts:
        unique_employee_roles = list(set([e["role"] for e in employees]))
        if not unique_employee_roles:
            unique_employee_roles = ["worker"]
            
        days = range(7)
        for d in days:
            date = (datetime.fromisoformat(start_date_str) + timedelta(days=d)).date().isoformat()
            for role in unique_employee_roles:
                # 1 shift in the morning, 1 in the afternoon per role
                required_shifts.extend([
                    {"id": f"s_{d}_m_{role}", "date": date, "start_time": "08:00", "end_time": "14:00", "role": role},
                    {"id": f"s_{d}_a_{role}", "date": date, "start_time": "14:00", "end_time": "20:00", "role": role},
                ])

    # 2. Variables
    # x[(e, s)] is true if employee e works on shift s
    x = {}
    unassigned = {} # slack variables for soft coverage
    affinity_map = {}
    
    for s_idx, shift in enumerate(required_shifts):
        unassigned[s_idx] = model.NewBoolVar(f'unassigned_{s_idx}')

    for e_idx, emp in enumerate(employees):
        for s_idx, shift in enumerate(required_shifts):
            x[(e_idx, s_idx)] = model.NewBoolVar(f'x_{e_idx}_{s_idx}')
            
            # Predict affinity for this assignment
            affinity = scorer.predict_affinity(emp, shift, all_roles)
            affinity_map[(e_idx, s_idx)] = int(affinity * 100) # Scale for integer optimization

    # 3. Constraints
    
    # A. Each shift must be assigned to ONE employee OR be marked as unassigned
    for s_idx, shift in enumerate(required_shifts):
        model.Add(sum(x[(e_idx, s_idx)] for e_idx in range(len(employees))) + unassigned[s_idx] == 1)

    # B. Role Matching & Unavailability
    for e_idx, emp in enumerate(employees):
        for s_idx, shift in enumerate(required_shifts):
            # i. Role match
            if emp["role"] != shift["role"]:
                model.Add(x[(e_idx, s_idx)] == 0)
            
            # ii. Unavailability match
            for unav in unavailabilities:
                if unav["employee_id"] == emp["id"] and unav["date"] == shift["date"]:
                    model.Add(x[(e_idx, s_idx)] == 0)

    # C. No Overlapping Shifts & 11h Rest for the same employee
    def get_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    for e_idx in range(len(employees)):
        for s1_idx, s1 in enumerate(required_shifts):
            for s2_idx, s2 in enumerate(required_shifts):
                if s1_idx == s2_idx: continue
                
                start1, end1 = get_minutes(s1["start_time"]), get_minutes(s1["end_time"])
                start2, end2 = get_minutes(s2["start_time"]), get_minutes(s2["end_time"])
                
                if s1["date"] == s2["date"]:
                    # Overlap check
                    if s1_idx < s2_idx and max(start1, start2) < min(end1, end2):
                        model.Add(x[(e_idx, s1_idx)] + x[(e_idx, s2_idx)] <= 1)
                else:
                    # Inter-day rest check (11 hours = 660 mins)
                    d1 = datetime.fromisoformat(s1["date"])
                    d2 = datetime.fromisoformat(s2["date"])
                    if d2 == d1 + timedelta(days=1):
                        # s1 is Mon, s2 is Tue. Rest = (start2 + 24*60) - end1
                        rest_minutes = (start2 + 1440) - end1
                        if rest_minutes < 660:
                            model.Add(x[(e_idx, s1_idx)] + x[(e_idx, s2_idx)] <= 1)

    # D. Labor Law: Max 5 shifts per week (relaxed if needed, but keeping for now)
    for e_idx in range(len(employees)):
        model.Add(sum(x[(e_idx, s_idx)] for s_idx in range(len(required_shifts))) <= 5)

    # 4. Objective: Maximize total affinity - large penalty for unassigned shifts
    penalty_per_unassigned = 1000 # Heavily prioritize coverage
    model.Maximize(
        sum(x[(e_idx, s_idx)] * affinity_map[(e_idx, s_idx)] 
            for e_idx in range(len(employees)) 
            for s_idx in range(len(required_shifts)))
        - sum(unassigned[s_idx] * penalty_per_unassigned for s_idx in range(len(required_shifts)))
    )

    # 5. Solve
    solver = cp_model.CpSolver()
    # Enable parallelism: Use 8 workers to match the target 4-CPU Cloud Run instance (2 threads/core)
    solver.parameters.num_search_workers = 8
    # Set a time limit of 30 seconds to prevent timeouts on complex schedules
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        results = []
        for s_idx, shift in enumerate(required_shifts):
            for e_idx, emp in enumerate(employees):
                if solver.Value(x[(e_idx, s_idx)]):
                    results.append({
                        "id": shift["id"],
                        "date": shift["date"],
                        "employee_id": emp["id"],
                        "employee_name": emp["name"],
                        "start_time": shift["start_time"],
                        "end_time": shift["end_time"],
                        "role": shift["role"],
                        "affinity": affinity_map.get((e_idx, s_idx), 0) / 100.0
                    })
        return results
    return None

