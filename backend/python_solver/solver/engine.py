from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import numpy as np
from utils.status_manager import update_status, set_running

def solve_schedule(employees: list, required_shifts: list, unavailabilities: list, constraints: dict, start_date_str: str, end_date_str: str, activities: list = [], environment: str = "default"):
    """
    Agentic Solver: Handles variable shift durations, overlap detection,
    and role-based constraints.
    Integrates NeuralScorer for soft-constraint optimization.
    Now loads configuration from Datastore if available.
    """
    set_running(True)
    try:
        from scorer.model import NeuralScorer
        from utils.datastore_helper import get_db

        # Load configuration
        client = get_db()
        key = client.key("AlgorithmConfig", environment)
        entity = client.get(key)

        affinity_weight = 1.0
        penalty_unassigned = 100
        if entity:
            affinity_weight = entity.get("affinity_weight", 1.0)
            penalty_unassigned = int(float(entity.get("penalty_unassigned", 100) or 100))
            print(f"DEBUG: Using custom config for {environment}: affinity_weight={affinity_weight}, penalty_unassigned={penalty_unassigned}")

        # Load Data Mappings (Vital for Inference)
        key_map = client.key("DataMapping", environment)
        entity_map = client.get(key_map)
        env_mappings = entity_map.get("mappings") if entity_map else None
        
        if env_mappings:
             print(f"DEBUG: Loaded {len(env_mappings)} custom data mappings for inference. Keys: {list(env_mappings.keys())[:5]}")
        else:
             print(f"WARNING: No DataMapping found for {environment}. Using defaults.")

        scorer = NeuralScorer()
        scorer.refresh_if_needed(force=True) # Auto-implement latest GCS weights if updated

        # Load Labor Profiles for this environment
        # Build a lookup: profile_id -> profile_data
        labor_profiles = {}
        query = client.query(kind="LaborProfile")
        for profile_entity in query.fetch():
            profile_id = profile_entity.key.name
            labor_profiles[profile_id] = {
                "max_weekly_hours": profile_entity.get("max_weekly_hours", 40.0),
                "max_daily_hours": profile_entity.get("max_daily_hours", 8.0),
                "max_consecutive_days": profile_entity.get("max_consecutive_days", 6),
                "min_rest_hours": profile_entity.get("min_rest_hours", 11.0)
            }
        
        print(f"DEBUG: Loaded {len(labor_profiles)} Labor Profiles for constraint customization.")

        # Get all unique roles for feature extraction (Normalized)
        all_roles = sorted(list(set([str(s.get("role") or "").strip().upper() for s in required_shifts] + [str(e.get("role") or "").strip().upper() for e in employees])))

        # -------------------
        update_status(message=f"Starting Solver for {environment}", progress=0.1, phase="OPTIMIZATION", log=f"Solving {len(required_shifts)} shifts for {len(employees)} employees...")

        model = cp_model.CpModel()

        # 1. Dynamic Demand Generation (Learned from history)
        if not required_shifts:
            from utils.demand_profiler import get_demand_profile
            profile = get_demand_profile(environment)

            unique_employee_roles = list(set([e["role"] for e in employees]))
            if not unique_employee_roles:
                unique_employee_roles = ["worker"]

            start_dt = datetime.fromisoformat(start_date_str)
            end_dt = datetime.fromisoformat(end_date_str)
            num_days = (end_dt - start_dt).days + 1

            # We also need activities to match IDs from profile
            # Use provided activities; only initialize if None
            if activities is None:
                activities = []
            
            # (Old overwrite bug removed)

            for d in range(num_days):
                current_date = (start_dt + timedelta(days=d))
                date_str = current_date.date().isoformat()
                dow = str(current_date.weekday())

                # If we have a profile for this company, use it
                if profile:
                    for act_id, dow_patterns in profile.items():
                        if dow in dow_patterns:
                            slots = dow_patterns[dow] # This is now a LIST of {start, end, qty}
                            if isinstance(slots, dict): slots = [slots] # Backward compatibility

                            # Find activity info
                            act_info = next((a for a in activities if str(a.get("id")) == str(act_id)), None)

                            for p in slots:
                                qty = p.get("quantity", 1)
                                for s_idx in range(qty):
                                    required_shifts.append({
                                        "id": f"learned_{act_id}_{date_str}_{p['start_time'].replace(':','')}_slot_{s_idx}",
                                        "date": date_str,
                                        "start_time": p["start_time"],
                                        "end_time": p["end_time"],
                                        "role": p.get("role", "worker"),
                                        "activity_id": act_id,
                                        "project": act_info.get("project") if act_info else None
                                    })
                else:
                    # Fallback to smart defaults
                    # Fallback to smart defaults (Scaled to workforce)
                    # If we have 10 employees, generate ~8 shifts to show a realistic schedule
                    import random
                    target_utilization = 0.8 # 80% of staff working
                    total_emp_count = len(employees)
                    shifts_needed = max(2, int(total_emp_count * target_utilization))
                    
                    # Distribute needed shifts across roles
                    for i in range(shifts_needed):
                        # Round-robin or random role assignment if multiple roles exist
                        r_idx = i % len(unique_employee_roles)
                        role = unique_employee_roles[r_idx]
                        
                        # Split M/A (Morning/Afternoon)
                        is_morning = i % 2 == 0
                        
                        if is_morning:
                             required_shifts.append({
                                "id": f"fallback_{date_str}_m_{i}_{role}", 
                                "date": date_str, 
                                "start_time": "08:00", 
                                "end_time": "14:00", 
                                "role": role
                            })
                        else:
                             required_shifts.append({
                                "id": f"fallback_{date_str}_a_{i}_{role}", 
                                "date": date_str, 
                                "start_time": "14:00", 
                                "end_time": "20:00", 
                                "role": role
                            })
            
            # Update status with actual generated count
            update_status(message=f"Solving {len(required_shifts)} Auto-Generated Shifts", progress=0.2, phase="OPTIMIZATION", log=f"Generated {len(required_shifts)} shifts from demand profile...")

        # 2. Variables & Batch Neural Prediction
        x = {}
        unassigned = {} # slack variables for soft coverage
        affinity_map = {}

        for s_idx, shift in enumerate(required_shifts):
            unassigned[s_idx] = model.NewBoolVar(f'unassigned_{s_idx}')

        print(f"DEBUG: Extracting features for {len(employees) * len(required_shifts)} pairs...")
        all_features = []
        pairs = []

        def norm_role(r):
            return str(r or "").strip().upper()

        for e_idx, emp in enumerate(employees):
            e_role = norm_role(emp.get("role"))
            for s_idx, shift in enumerate(required_shifts):
                s_role = norm_role(shift.get("role"))
                # i. Preliminary Check: Flexible Role Matching
                # Allow partial match (e.g. "SENIOR DEVELOPER" matches "DEVELOPER")
                if e_role == s_role or (e_role in s_role) or (s_role in e_role):
                    feat = scorer.extract_features(emp, shift, mappings=env_mappings)
                    all_features.append(feat)
                    if len(all_features) == 1:
                        print(f"DEBUG: Sample Feature Vector[0]: {feat}")
                    pairs.append((e_idx, s_idx))
                else:
                    affinity_map[(e_idx, s_idx)] = 0
                
                # IMPORTANT: Always create the decision variable!
                x[(e_idx, s_idx)] = model.NewBoolVar(f'x_{e_idx}_{s_idx}')

            if e_idx % 10 == 0:
                update_status(log=f"Extracted features for {emp.get('fullName', '???')}...")

        if all_features and scorer.enabled and scorer.model:
            update_status(message="Computing Neural Affinities...", progress=0.3, log=f"Running inference for {len(all_features)} pairs...")
            X_batch = np.array(all_features)
            
            # Use HYBRID BATCH prediction to enforce safety heuristics (Avoid 0% confidence)
            preds = scorer.predict_batch(X_batch)
            
            # DEBUG INFER: Critical for verifying model output
            print(f"DEBUG INFER: Generated {len(preds)} predictions.")
            print(f"DEBUG INFER: Mean Score={np.mean(preds):.4f}, Max={np.max(preds):.4f}, Min={np.min(preds):.4f}")
            print(f"DEBUG INFER: First 5 scores: {[float(p[0]) for p in preds[:5]]}")
            if len(preds) > 0:
                print(f"DEBUG: Raw Prediction Sample: {preds[0]} -> {int(preds[0][0] * 100)}%")
                
            # Helper for safe conversion
            def safe_int(val, default=0):
                try:
                    if val is None: return default
                    if isinstance(val, (float, np.floating)):
                        if np.isnan(val) or np.isinf(val): return default
                    return int(val)
                except: return default

            for idx, (e_idx, s_idx) in enumerate(pairs):
                aff = safe_int(preds[idx][0] * 100)
                affinity_map[(e_idx, s_idx)] = aff

            avg_aff = sum(affinity_map.values()) / max(len(affinity_map), 1)
            update_status(log=f"Inference complete. Avg Affinity: {avg_aff:.1f}%")
            print(f"DEBUG: Calculated {len(affinity_map)} affinities. Avg: {avg_aff:.1f}%")
        else:
            # Fallback for when no features are extracted (or no role matches)
            # If it's a role match but no model, give 50%.
            # Actually pairs only contains role matches.
            for e_idx, s_idx in pairs:
                if (e_idx, s_idx) not in affinity_map:
                    affinity_map[(e_idx, s_idx)] = 50

        update_status(message="Building CP-SAT Model...", progress=0.5, log="Adding constraints (Rest, Overlap, Roles)...")

        try:
            # 3. Constraints

            # A. Each shift must be assigned to ONE employee OR be marked as unassigned
            for s_idx, shift in enumerate(required_shifts):
                model.Add(sum(x[(e_idx, s_idx)] for e_idx in range(len(employees))) + unassigned[s_idx] == 1)

            # B. Role Matching & Unavailability
            for e_idx, emp in enumerate(employees):
                e_role = norm_role(emp.get("role"))
                for s_idx, shift in enumerate(required_shifts):
                    s_role = norm_role(shift.get("role"))
                    
                    # i. Role match (Keep consistent with preliminary check)
                    # Force x=0 ONLY if roles are completely incompatible
                    if not (e_role == s_role or (e_role in s_role) or (s_role in e_role)):
                        model.Add(x[(e_idx, s_idx)] == 0)

                    # ii. Contract Validity: employment.dtHired <= Data Turno <= employment.dtDismissed
                    shift_date = datetime.fromisoformat(shift["date"]).date()
                    if emp.get("dtHired"):
                        try:
                            hired_date = datetime.fromisoformat(emp["dtHired"]).date()
                            if shift_date < hired_date:
                                model.Add(x[(e_idx, s_idx)] == 0)
                        except: pass

                    if emp.get("dtDismissed"):
                        try:
                            dismissed_date = datetime.fromisoformat(emp["dtDismissed"]).date()
                            if shift_date > dismissed_date:
                                model.Add(x[(e_idx, s_idx)] == 0)
                        except: pass

                    # iii. Unavailability match
                    for unav in unavailabilities:
                        if unav["employee_id"] == emp["id"] and unav["date"] == shift["date"]:
                            model.Add(x[(e_idx, s_idx)] == 0)

        except Exception as e:
            import traceback
            print(f"CRITICAL SOLVER ERROR: {e}")
            traceback.print_exc()
            raise e

        # C. No Overlapping Shifts & 11h Rest for the same employee
        def get_minutes(t_str):
            h, m = map(int, t_str.split(':'))
            return h * 60 + m

        # Pre-calculate minutes and group shifts by day
        shift_details = []
        shifts_by_day = {} # date_str -> list of indices
        for s_idx, s in enumerate(required_shifts):
            d = get_minutes(s["start_time"])
            e = get_minutes(s["end_time"])
            shift_details.append((d, e, datetime.fromisoformat(s["date"])))
            date_str = s["date"]
            if date_str not in shifts_by_day: shifts_by_day[date_str] = []
            shifts_by_day[date_str].append(s_idx)

        all_dates = sorted(shifts_by_day.keys())

        for e_idx in range(len(employees)):
            # i. Intra-day: No overlap
            for date_str, s_indices in shifts_by_day.items():
                for i in range(len(s_indices)):
                    for j in range(i + 1, len(s_indices)):
                        idx1, idx2 = s_indices[i], s_indices[j]
                        start1, end1, _ = shift_details[idx1]
                        start2, end2, _ = shift_details[idx2]
                        if max(start1, start2) < min(end1, end2):
                            model.Add(x[(e_idx, idx1)] + x[(e_idx, idx2)] <= 1)

            # ii. Inter-day: 11h Rest between consecutive days
            for d_idx in range(len(all_dates) - 1):
                date1 = all_dates[d_idx]
                date2 = all_dates[d_idx + 1]
                # Only if they are consecutive calendar days
                dt1 = datetime.fromisoformat(date1)
                dt2 = datetime.fromisoformat(date2)
                if dt2 == dt1 + timedelta(days=1):
                    for idx1 in shifts_by_day[date1]:
                        for idx2 in shifts_by_day[date2]:
                            _, end1, _ = shift_details[idx1]
                            start2, _, _ = shift_details[idx2]
                            rest_minutes = (start2 + 1440) - end1
                            if rest_minutes < 660:
                                model.Add(x[(e_idx, idx1)] + x[(e_idx, idx2)] <= 1)

        # D. Labor Law: Max hours per week (Per-Employee via Labor Profiles)
        for e_idx, emp in enumerate(employees):
            # Resolve employee's specific profile
            profile_id = emp.get("labor_profile_id")
            if profile_id and profile_id in labor_profiles:
                profile = labor_profiles[profile_id]
                max_weekly_hours = profile["max_weekly_hours"]
                # TODO: Also apply max_daily_hours, max_consecutive_days, min_rest_hours
            else:
                # Fallback to company/global default
                max_weekly_hours = entity.get("max_hours_weekly") if entity else 40.0
            
            max_minutes_weekly = safe_int(max_weekly_hours * 60, 2400)
            
            # Group shift indices by (Year, WeekNumber)
            work_by_week = {} # (year, week) -> [minutes_expressions]
            for s_idx, _ in enumerate(required_shifts):
                d_obj = shift_details[s_idx][2]
                yw = d_obj.isocalendar()[:2] # (year, week)
                if yw not in work_by_week: work_by_week[yw] = []
                
                start, end, _ = shift_details[s_idx]
                duration = end - start
                if duration < 0: duration += 1440
                work_by_week[yw].append(x[(e_idx, s_idx)] * duration)
            
            # Apply limit per week
            for yw, minutes in work_by_week.items():
                model.Add(sum(minutes) <= max_minutes_weekly)

        # 4. Objective: Maximize total affinity - large penalty for unassigned shifts
        model.Maximize(
            sum(x[(e_idx, s_idx)] * int(affinity_map[(e_idx, s_idx)] * affinity_weight)
                for e_idx in range(len(employees))
                for s_idx in range(len(required_shifts)))
            - sum(unassigned[s_idx] * int(penalty_unassigned) for s_idx in range(len(required_shifts)))
        )

        # 5. Solve
        solver = cp_model.CpSolver()
        # Enable parallelism: Use 8 workers to match the target 4-CPU Cloud Run instance (2 threads/core)
        solver.parameters.num_search_workers = 8
        # Set a time limit of 30 seconds to prevent timeouts on complex schedules
        solver.parameters.max_time_in_seconds = 30.0
        update_status(message="Executing Combinatorial Optimization...", progress=0.8, log=f"Searching for solution (8 workers, 30s limit)...")
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            update_status(message="Schedule Solution Found", progress=1.0, phase="IDLE", log=f"Solution status: {'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'}")
            results = []
            for s_idx, shift in enumerate(required_shifts):
                assigned = False
                for e_idx, emp in enumerate(employees):
                    if solver.Value(x[(e_idx, s_idx)]):
                        results.append({
                            "id": shift["id"],
                            "date": shift["date"],
                            "employee_id": emp.get("id") or emp.get("employee_id") or emp.get("external_id"),
                            "employee_name": emp.get("fullName") or emp.get("name"),
                            "start_time": shift["start_time"],
                            "end_time": shift["end_time"],
                            "role": shift["role"],
                            "activity_id": shift.get("activity_id"),
                            "project": shift.get("project"),
                            "affinity": affinity_map.get((e_idx, s_idx), 0) / 100.0,
                            "is_unassigned": False
                        })
                        assigned = True
                        break # One employee per shift
                
                if not assigned:
                    # Include UNASSIGNED shifts so they appear in the UI (e.g. in a "To Assign" row)
                    results.append({
                        "id": shift["id"],
                        "date": shift["date"],
                        "employee_id": "unassigned", # Specific marker
                        "employee_name": "Unassigned",
                        "start_time": shift["start_time"],
                        "end_time": shift["end_time"],
                        "role": shift["role"],
                        "activity_id": shift.get("activity_id"),
                        "project": shift.get("project"),
                        "affinity": 0.0,
                        "is_unassigned": True
                    })

            assigned_count = len([r for r in results if not r.get('is_unassigned')])
            unassigned_count = len(results) - assigned_count
            update_status(
                message=f"Optimized: {assigned_count} Assigned, {unassigned_count} Open", 
                progress=1.0, 
                phase="IDLE", 
                log=f"Solution status: {'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'}. Assigned: {assigned_count}/{len(required_shifts)}."
            )

            return results

        update_status(message="Search Completed - No Solution", progress=1.0, phase="IDLE", log="Solver could not find a valid matching with current constraints.")
        return None
    finally:
        set_running(False)
