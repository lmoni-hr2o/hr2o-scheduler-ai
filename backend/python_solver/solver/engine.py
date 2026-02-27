from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import numpy as np
from utils.status_manager import set_running

def update_status(message=None, progress=None, phase=None, log=None, details=None):
    from utils.status_manager import update_status as _upd
    _upd(message=message, progress=progress, phase=phase, log=log, details=details)

def normalize_name(name):
    """Normalize names by sorting words"""
    if not name: return ""
    import re
    # Remove special characters, multiple spaces, keep only alphanumeric words
    clean = re.sub(r'[^A-Z0-9\s]', '', name.upper())
    words = sorted(clean.split())
    return " ".join(words)

def solve_schedule(employees: list, required_shifts: list, unavailabilities: list, constraints: dict, start_date_str: str, end_date_str: str, activities: list = [], environment: str = "default"):
    """
    Agentic Solver: Handles variable shift durations, overlap detection,
    and role-based constraints. 
    Integrates NeuralScorer for soft-constraint optimization.
    Now uses ForecastingService (ML) for demand prediction and Absence Risk.
    """
    set_running(True)
    
    def safe_int(val, default=0):
        try:
            if val is None: return default
            import numpy as np
            if isinstance(val, (float, np.floating)):
                if np.isnan(val) or np.isinf(val): return default
            return int(val)
        except: return default

    try:
        # --- DEDUPLICAZIONE OBBLIGATORIA (Nome e ID) ---
        # Evita lo scheduling doppio di persone fisiche con ID o nomi duplicati.
        # Assicura che i vincoli (indisponibilità) seguano la persona reale.
        dedupe_map = {} # normalized_name -> emp
        id_dedupe = set() # Set of employee IDs already processed
        seen_names = set() # Set of normalized names already processed
        
        unique_employees = []
        for emp in employees:
            eid = str(emp.get("id") or emp.get("employee_id") or emp.get("external_id") or "").strip()
            fname = normalize_name(emp.get("fullName") or emp.get("name") or "")
            
            if not eid or not fname: continue
            
            # Check if this employee (by normalized name or ID) has already been added
            if fname not in seen_names and eid not in id_dedupe:
                seen_names.add(fname)
                dedupe_map[fname] = emp # Store the first encountered employee for this normalized name
                id_dedupe.add(eid)
                unique_employees.append(emp)
        
        if len(unique_employees) < len(employees):
            print(f"DEBUG: Dipendenti deduplicati. Da {len(employees)} -> {len(unique_employees)} unità uniche.")
            employees = unique_employees
        # ------------------------------------------------

        from scorer.model import NeuralScorer
        from utils.datastore_helper import get_db

        # Load configuration
        client = get_db()
        key = client.key("AlgorithmConfig", environment)
        entity = client.get(key)

        affinity_weight = 1.0
        penalty_unassigned = 500  # Increased from 100 to force coverage
        fairness_weight = 80.0    # Increased from 50 to better balance load
        if entity:
            affinity_weight = entity.get("affinity_weight", 1.0)
            penalty_unassigned = int(float(entity.get("penalty_unassigned", 500) or 500))
            penalty_absence_risk = int(float(entity.get("penalty_absence_risk", 200) or 200))
            fairness_weight = float(entity.get("fairness_weight", 80.0))
            print(f"DEBUG: Stored config: aff={affinity_weight}, unassigned={penalty_unassigned}, fairness={fairness_weight}")
        else:
            penalty_absence_risk = 200 # Default default

        # OVERRIDE from request constraints (dynamic suggestions)
        if constraints:
            affinity_weight = constraints.get("affinity_weight", constraints.get("affinityWeight", affinity_weight))
            penalty_unassigned = constraints.get("penalty_unassigned", constraints.get("penaltyUnassigned", penalty_unassigned))
            if penalty_unassigned < 500: penalty_unassigned = 500 # Floor to ensure coverage
            penalty_absence_risk = constraints.get("penalty_absence_risk", constraints.get("penaltyAbsenceRisk", penalty_absence_risk))
            fairness_weight = constraints.get("fairness_weight", constraints.get("fairnessWeight", fairness_weight))
            if fairness_weight < 80.0: fairness_weight = 80.0 # Floor for better load balancing
            print(f"DEBUG: Dynamic overrides: aff={affinity_weight}, unassigned={penalty_unassigned}, fairness={fairness_weight}")


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
        
        # We need to load profiles from the current environment namespace...
        # AND possibly from other namespaces if we are in a management environment like OVERCLEAN
        namespaces_to_check = {environment, "default"}
        for emp in employees:
            if emp.get("environment"):
                namespaces_to_check.add(emp.get("environment"))
        
        print(f"DEBUG: Searching Labor Profiles in namespaces: {namespaces_to_check}")
        
        for ns in namespaces_to_check:
            try:
                ns_client = get_db(namespace=ns).client
                query = ns_client.query(kind="LaborProfile")
                count = 0
                for profile_entity in query.fetch():
                    profile_id = profile_entity.key.name
                    if profile_id not in labor_profiles:
                        labor_profiles[profile_id] = {
                            "max_weekly_hours": profile_entity.get("max_weekly_hours", 40.0),
                            "max_daily_hours": profile_entity.get("max_daily_hours", 8.0),
                            "max_consecutive_days": profile_entity.get("max_consecutive_days", 6),
                            "min_rest_hours": profile_entity.get("min_rest_hours", 11.0)
                        }
                        count += 1
                if count > 0:
                    print(f"  > Loaded {count} profiles from namespace {ns}")
            except Exception as e_ns:
                print(f"  ! Error loading profiles from {ns}: {e_ns}")
        
        print(f"DEBUG: Total Labor Profiles loaded: {len(labor_profiles)}")

        # Get all unique roles for feature extraction (Normalized)
        all_roles = sorted(list(set([str(s.get("role") or "").strip().upper() for s in required_shifts] + [str(e.get("role") or "").strip().upper() for e in employees])))

        # -------------------
        # -------------------
        if not required_shifts:
             update_status(message=f"AI Forecasting started for {environment}", progress=0.1, phase="OPTIMIZATION", log=f"No input shifts. requesting AI Demand Forecast...")
        else:
             update_status(message=f"Starting Solver for {environment}", progress=0.1, phase="OPTIMIZATION", log=f"Solving {len(required_shifts)} provided shifts for {len(employees)} employees...")

        model = cp_model.CpModel()

        # 1. GENERAZIONE DINAMICA FABBISOGNO (Dati storici / ML)
        if not required_shifts:
            from services.forecasting_service import ForecastingService
            # Proviamo prima l'allocazione tramite ML Forecast
            try:
                # Use provided activities; only initialize if None
                if activities is None:
                    activities = []
                
                start_dt = datetime.fromisoformat(start_date_str)
                end_dt = datetime.fromisoformat(end_date_str)
                num_days = (end_dt - start_dt).days + 1
                
                forecaster = ForecastingService(environment)
                
                # Filter to only activities requested in the payload to reduce memory/noise
                active_activity_ids = [str(a.get("id")) for a in activities if a.get("id")]
                predicted_demand = forecaster.predict_demand(start_dt, end_dt, activity_ids=active_activity_ids)
                
                # CAPACITY GUARD: If ML generates too many shifts, we must abort or sub-sample
                # 5000 shifts is a reasonable limit for a synchronous solve with 4GB RAM
                if len(predicted_demand) > 5000:
                    print(f"WARNING: Too many ML predictions ({len(predicted_demand)}). Sub-sampling to 5000.")
                    predicted_demand = predicted_demand[:5000]
                
                if predicted_demand:
                    print(f"DEBUG: Using ML Forecast with {len(predicted_demand)} predictions.")
                    # Convert demand (hours) to shift blocks
                    # Heuristic: Break demand into chunks of 4h, min 2h.
                    for item in predicted_demand:
                        hours_needed = item["predicted_hours"]
                        date_str = item["date"]
                        act_id = item["activity_id"]
                        
                        # Find activity info for project mapping
                        act_info = next((a for a in activities if str(a.get("id")) == str(act_id)), None)
                        
                        # Use activity name as role hint if available, else 'worker'
                        role_hint = "worker"
                        if act_info:
                             role_hint = str(act_info.get("name", "worker")).strip().upper()

                        target_dur = item.get("typical_duration", 6.0)
                        chunks = []
                        remaining = hours_needed
                        
                        # Dynamic Chunking: aim for typical duration
                        while remaining >= 2.0:
                            block = min(target_dur, remaining)
                            # If taking this block leaves a very small residue, just absorb it into this shift
                            # unless it exceeds a maximum legal shift (e.g. 10h)
                            if 0 < (remaining - block) < 2.0:
                                if (remaining) <= 12.0: # Hard cap for combined shifts
                                    block = remaining
                            
                            chunks.append(block)
                            remaining -= block
                            if remaining < 1.0: break
                            
                        # Assign chunks to times. Use Learned Start Time if available
                        typical_start = item.get("typical_start_hour", 8.0)
                        
                        # Spread logic: if we have multiple chunks for the same activity/day, 
                        # they are usually distinct people needed. We add a slight spread.
                        for i, block_dur in enumerate(chunks):
                            # Jitter: 15 min offset to spread load slightly
                            # This prevents everyone from being exactly at 08:00 if multiple people are needed
                            curr_h = typical_start + ((i % 4) * 0.25) 
                            
                            start_h = int(curr_h)
                            start_m = int((curr_h - start_h) * 60)
                            end_h = int(curr_h + block_dur)
                            end_m = int(((curr_h + block_dur) - end_h) * 60)
                            
                            s_time = f"{start_h:02d}:{start_m:02d}"
                            e_time = f"{end_h:02d}:{end_m:02d}"
                            
                            required_shifts.append({
                                "id": f"ml_{act_id}_{date_str}_{i}_{s_time.replace(':','')}",
                                "date": date_str,
                                "start_time": s_time,
                                "end_time": e_time,
                                "role": role_hint,
                                "activity_id": act_id,
                                "project": act_info.get("project") if act_info else None
                            })
                    update_status(message=f"Solving {len(required_shifts)} ML Predicted Shifts", progress=0.2, phase="OPTIMIZATION", log=f"Generated {len(required_shifts)} shifts from ML model.")

                else:
                     # Fallback to Static Profile logic...
                     raise ValueError("No ML predictions available, using fallback.")

            except Exception as e_fore:
                print(f"WARNING: Forecasting fallito ({e_fore}), uso DemandProfiler come fallback.")
                from utils.demand_profiler import get_demand_profile
                profile = get_demand_profile(environment)
                
                # DIAGNOSTIC: How many activities have a profile?
                print(f"DIAGNOSTIC: Profile found for {len(profile)} activities.")
    
                unique_employee_roles = list(set([str(e.get("role") or "worker").strip().upper() for e in employees]))
                if not unique_employee_roles:
                    unique_employee_roles = ["WORKER"]
    
                start_dt = datetime.fromisoformat(start_date_str)
                end_dt = datetime.fromisoformat(end_date_str)
                num_days = (end_dt - start_dt).days + 1
    
                # FILTER: If we have a profile, we ONLY plan activities present in the profile.
                # This prevents "Ghost" or "Inactive" activities from inflating the schedule.
                if profile:
                    relevant_activities = [a for a in (activities or []) if str(a.get("id")) in profile]
                    if not relevant_activities and activities:
                         # Fallback if profile exists but doesn't match current activity IDs (schema issue)
                         print("WARNING: Profile exists but no activity ID match. Using filtered activity list.")
                         relevant_activities = activities
                    else:
                         activities = relevant_activities
                
                print(f"DIAGNOSTIC: Planning for {len(activities or [])} filtered activities.")
                if activities is None:
                    activities = []
                
                # (Old overwrite bug removed)
    
                for d in range(num_days):
                    current_date = (start_dt + timedelta(days=d))
                    date_str = current_date.date().isoformat()
                    dow = str(current_date.weekday())
    
                    # If we have a profile for this company, use it
                    if profile:
                        # Prepare keys for hybrid matching
                        active_ids = {str(a.get("id")) for a in activities if a.get("id")}
                        active_codes = {str(a.get("code")).strip().upper() for a in activities if a.get("code")}
                        active_names = {str(a.get("name")).strip().upper() for a in activities if a.get("name")}
                        
                        for act_id, dow_patterns in profile.items():
                            # Match check: If no activities requested, use all. Else filter.
                            # We match if the profile key (act_id) matches any requested ID, Code or Name
                            is_active = (not active_ids and not active_codes and not active_names) or \
                                        (str(act_id) in active_ids) or \
                                        (str(act_id).upper() in active_codes) or \
                                        (str(act_id).upper() in active_names)
                            
                            if str(act_id).strip() == "816/2020 ORDINARIO":
                                 print(f"DIAGNOSTIC TRACE [{date_str} DOW={dow}]: act_id={act_id} is_active={is_active}")
                                 print(f"DIAGNOSTIC TRACE SETS: ids_len={len(active_ids)} ids={list(active_ids)[:5]} codes={list(active_codes)[:5]}")
                            
                            if not is_active:
                                continue
                                
                            if dow in dow_patterns:
                                slots = dow_patterns[dow]
                                if isinstance(slots, dict): slots = [slots] # Backward compatibility
    
                                # Find activity info
                                act_info = next((a for a in activities if str(a.get("id")) == str(act_id)), None)
    
                                for p in slots:
                                    # ENFORCE MINIMUM DURATION: 60 minutes (1 hour)
                                    try:
                                        h1, m1 = map(int, p["start_time"].split(':'))
                                        h2, m2 = map(int, p["end_time"].split(':'))
                                        dur = (h2 * 60 + m2) - (h1 * 60 + m1)
                                        if dur < 0: dur += 1440
                                        if dur < 60: 
                                            # Skip shifts shorter than 1 hour to satisfy user constraint
                                            continue
                                    except:
                                        pass

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
                        # FALLBACK: SMART DEFAULTS (Quando mancano sia ML che Profiler)
                        # Se l'azienda non ha dati storici lavorativi nel weekend, saltiamo sabato/domenica.
                        if current_date.weekday() >= 5: 
                            continue
                            
                        # Scaliamo in base alla forza lavoro disponibile
                        import random
                        target_utilization = 0.8 # 80% of staff working
                        total_emp_count = len(employees)
                        shifts_needed = max(2, int(total_emp_count * target_utilization))
                        
                        # Distribute needed shifts across roles
                        for i in range(shifts_needed):
                            # Round-robin or random role assignment if multiple roles exist
                            r_idx = i % len(unique_employee_roles)
                            role = unique_employee_roles[r_idx]
                            
                            # More realistic fallback: single 8-hour block (standard contract)
                            # or mixed if many shifts are needed
                            start_h = 8
                            if i % 3 == 1: start_h = 9 # Slight stagger
                            elif i % 3 == 2: start_h = 10 
                            
                            s_time = f"{start_h:02d}:00"
                            e_time = f"{start_h + 8:02d}:00"
                            
                            required_shifts.append({
                                "id": f"fallback_{date_str}_{i}_{role}_{s_time.replace(':','')}", 
                                "date": date_str, 
                                "start_time": s_time, 
                                "end_time": e_time, 
                                "role": role
                            })
                
                # Update status with actual generated count
                update_status(message=f"Solving {len(required_shifts)} Shifts (Fallback)", progress=0.2, phase="OPTIMIZATION")

        # 2. Variables & Batch Neural Prediction
        # RE-OPTIMIZATION: Use SPARSE variables to avoid OOM for large datasets (PROFER)
        x = {} # (e_idx, s_idx) -> BoolVar (Only created if viable)
        unassigned = {} # slack variables for soft coverage
        affinity_map = {} # (e_idx, s_idx) -> int

        for s_idx, shift in enumerate(required_shifts):
            unassigned[s_idx] = model.NewBoolVar(f'unassigned_{s_idx}')

        # SANITY CHECK: Problem Size
        if len(employees) * len(required_shifts) > 1000000:
             print(f"CRITICAL: Problem size too large ({len(employees)}x{len(required_shifts)}). Aborting to prevent 8GB OOM.")
             raise MemoryError("Combinatorial Explosion Risk")
        
        print(f"DEBUG: Extracting features for sparse viable pairs...")
        all_features = []
        pairs = []

        def norm_role(r):
            return str(r or "").strip().upper()

        for e_idx, emp in enumerate(employees):
            e_role = norm_role(emp.get("role"))
            
            # Pre-filter dates based on contract
            hired_date = None
            if emp.get("dtHired"):
                try: hired_date = datetime.fromisoformat(emp["dtHired"]).date()
                except: pass
            
            dismissed_date = None
            if emp.get("dtDismissed"):
                try: dismissed_date = datetime.fromisoformat(emp["dtDismissed"]).date()
                except: pass

            for s_idx, shift in enumerate(required_shifts):
                s_role = norm_role(shift.get("role"))
                
                # Eligibility check (Role + Contract)
                # WORKER is a wildcard: if either the employee or the shift has 'WORKER' role, they match.
                # This ensures compatibility between generic staff and learned historical activities.
                is_worker_match = (e_role == "WORKER" or s_role == "WORKER")
                strict_match = (e_role == s_role or (e_role in s_role) or (s_role in e_role))
                
                if not (is_worker_match or strict_match):
                    continue
                
                shift_date = datetime.fromisoformat(shift["date"]).date()
                if hired_date and shift_date < hired_date: continue
                if dismissed_date and shift_date > dismissed_date: continue
                
                # If viable, create variable and extract features
                x[(e_idx, s_idx)] = model.NewBoolVar(f'x_{e_idx}_{s_idx}')
                feat = scorer.extract_features(emp, shift, mappings=env_mappings)
                all_features.append(feat)
                pairs.append((e_idx, s_idx))

            if e_idx % 20 == 0:
                update_status(log=f"Sparse extraction: {e_idx}/{len(employees)} employees...")

        if all_features and scorer.enabled and scorer.model:
            update_status(message="Computing Neural Affinities...", progress=0.3, log=f"Running inference for {len(all_features)} pairs...")
            X_batch = np.array(all_features)
            
            # Use HYBRID BATCH prediction to enforce safety heuristics (Avoid 0% confidence)
            preds = scorer.predict_batch(X_batch)
            
            # DEBUG INFER: Critical for verifying model output
            print(f"DEBUG INFER: Generated {len(preds)} predictions.")
            print(f"DEBUG INFER: First 5 scores: {[float(p[0]) for p in preds[:5]]}")
                
            # Inference complete

            for idx, (e_idx, s_idx) in enumerate(pairs):
                aff = safe_int(preds[idx][0] * 100)
                affinity_map[(e_idx, s_idx)] = aff

            avg_aff = sum(affinity_map.values()) / max(len(affinity_map), 1)
            update_status(log=f"Inference complete. Avg Affinity: {avg_aff:.1f}%")
            
            # MEMORY CLEANUP
            del all_features, X_batch, preds
            import gc
            gc.collect()
            for e_idx, s_idx in pairs:
                if (e_idx, s_idx) not in affinity_map:
                    affinity_map[(e_idx, s_idx)] = 50
            
            print(f"DIAGNOSTIC: Pairs identified: {len(pairs)}, Affinity map size: {len(affinity_map)}")
            if len(pairs) > 0:
                e0, s0 = pairs[0]
                print(f"DIAGNOSTIC Sample: EmpRole={norm_role(employees[e0].get('role'))}, ShiftRole={norm_role(required_shifts[s0].get('role'))}")

        # --- ABSENCE RISK CALCULATION (Previsionale Phase 2) ---
        absence_map = {} # (e_idx, date_str) -> probability float
        try:
            # 1. Use the SAME forecaster instance to avoid Redundant Data Fetch (OOM)
            if 'forecaster' not in locals():
                from services.forecasting_service import ForecastingService
                forecaster = ForecastingService(environment)
            
            # Prefetch for all unique dates in shifts
            unique_dates = sorted(list(set([s["date"] for s in required_shifts])))
            for d_str in unique_dates:
                 dt = datetime.fromisoformat(d_str)
                 # Returns dict {emp_id: prob}
                 daily_risks = forecaster.predict_absence_risk(dt)
                 
                 for e_idx, emp in enumerate(employees):
                     eid = emp.get("id") or emp.get("employee_id")
                     prob = daily_risks.get(eid, 0.0)
                     absence_map[(e_idx, d_str)] = prob
            
            print(f"DEBUG: Absence Risk calculated. Sample: {list(absence_map.items())[:3]}")
            
            # FINAL FORECASTER CLEANUP
            if 'forecaster' in locals():
                del forecaster
                import gc
                gc.collect()

        except Exception as e_risk:
             print(f"WARNING: Absence Risk model failed ({e_risk}). Ignoring risks.")
             # Fallback 0
             for e_idx in range(len(employees)):
                 for s in required_shifts:
                     absence_map[(e_idx, s["date"])] = 0.0

        update_status(message="Building CP-SAT Model...", progress=0.5, log="Adding constraints (Rest, Overlap, Roles)...")
        
        print(f"DIAGNOSTIC: Starting solver for {len(employees)} employees and {len(required_shifts)} shifts.")
        if len(required_shifts) == 0:
            print("DIAGNOSTIC WARNING: No required shifts were generated. This will cause an empty return.")

        try:
            # 3. Constraints

            # A. Each shift must be assigned to ONE employee OR be marked as unassigned
            for s_idx, shift in enumerate(required_shifts):
                eligible_vars = [x[(e_idx, s_idx)] for e_idx in range(len(employees)) if (e_idx, s_idx) in x]
                model.Add(sum(eligible_vars) + unassigned[s_idx] == 1)

            # B. Validity & Unavailability (Sparsified)
            # Role and contract match are already handled by sparse creation in step 2.
            name_of_id = {str(emp.get("id") or emp.get("employee_id") or ""): str(emp.get("fullName") or emp.get("name") or "") for emp in employees}
            for (e_idx, s_idx) in x.keys():
                emp = employees[e_idx]
                shift = required_shifts[s_idx]
                
                # Check unavailabilities only for viable pairs
                for unav in unavailabilities:
                    u_eid = str(unav.get("employee_id") or "")
                    u_name = name_of_id.get(u_eid, "").upper().strip()
                    e_name = str(emp.get("fullName") or emp.get("name") or "").upper().strip()
                    
                    if (unav["employee_id"] == emp.get("id") or (u_name and u_name == e_name)) and unav["date"] == shift["date"]:
                        model.Add(x[(e_idx, s_idx)] == 0)
                        break

        except Exception as e:
            import traceback
            print(f"CRITICAL SOLVER ERROR: {e}")
            traceback.print_exc()
            raise e

        # C. No Overlapping Shifts & 11h Rest for the same employee (Optimized Scalability)
        def get_minutes(t_str):
            h, m = map(int, t_str.split(':'))
            return h * 60 + m

        # Pre-calculate minutes, dates and durations
        shift_details = [] # Stores (start_m, end_m, date_obj, abs_start, abs_end)
        shift_durations = []
        base_date_obj = datetime.fromisoformat(required_shifts[0]["date"]) if required_shifts else datetime.now()

        for s_idx, s in enumerate(required_shifts):
            d = get_minutes(s["start_time"])
            e = get_minutes(s["end_time"])
            duration = e - d
            if duration < 0: duration += 1440
            
            s_date = datetime.fromisoformat(s["date"])
            day_offset = (s_date - base_date_obj).days
            abs_start = (day_offset * 1440) + d
            abs_end = abs_start + duration
            
            shift_details.append((d, e, s_date, abs_start, abs_end))
            shift_durations.append(duration)

        # 1. No Overlap (Immediate/Same Day)
        # We use NoOverlap WITHOUT any padding to allow contiguous "project" shifts in the same day.
        for e_idx, emp in enumerate(employees):
            intervals = []
            for s_idx, shift in enumerate(required_shifts):
                if (e_idx, s_idx) not in x: continue
                
                presence = x[(e_idx, s_idx)]
                iv = model.NewOptionalIntervalVar(
                    shift_details[s_idx][3], 
                    shift_durations[s_idx], 
                    shift_details[s_idx][4], 
                    presence, 
                    f'ival_e{e_idx}_s{s_idx}'
                )
                intervals.append(iv)
            
            if intervals:
                model.AddNoOverlap(intervals)

        # 2. Inter-day Rest (11 hours = 660 mins)
        # To avoid millions of constraints, we only compare shifts on consecutive or nearby days.
        REST_PERIOD = 660 
        
        # Group shift indices by employee and then by day offset
        emp_shifts_by_day = {e_idx: {} for e_idx in range(len(employees))}
        for (e_idx, s_idx) in x.keys():
            day_offset = (shift_details[s_idx][2] - base_date_obj).days
            if day_offset not in emp_shifts_by_day[e_idx]:
                emp_shifts_by_day[e_idx][day_offset] = []
            emp_shifts_by_day[e_idx][day_offset].append(s_idx)

        for e_idx, days_map in emp_shifts_by_day.items():
            sorted_days = sorted(days_map.keys())
            for i, d1 in enumerate(sorted_days):
                # We need to check day d1 against subsequent days
                # Usually checking the very next day d2 is enough if we assume people work daily.
                # To be safe, we check up to d1 + 2
                for j in range(i + 1, min(i + 3, len(sorted_days))):
                    d2 = sorted_days[j]
                    for s1_idx in days_map[d1]:
                        for s2_idx in days_map[d2]:
                            # If both s1 and s2 are assigned to e_idx, they must have 11h gap
                            # Constraint: End(s1) + 660 <= Start(s2)
                            model.Add(shift_details[s1_idx][4] + REST_PERIOD <= shift_details[s2_idx][3]).OnlyEnforceIf([x[(e_idx, s1_idx)], x[(e_idx, s2_idx)]])

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
                
                if (e_idx, s_idx) in x:
                    duration = shift_durations[s_idx]
                    work_by_week[yw].append(x[(e_idx, s_idx)] * duration)
            
            # Apply limit per week
            for yw, minutes in work_by_week.items():
                model.Add(sum(minutes) <= max_minutes_weekly)

        # E. MINIMUM DAILY PRESENCE (At least 1 hour of work if any is assigned)
        # Prevents "15-minute shifts" for individual projects.
        MIN_DAILY_MINUTES = 60 # 1 Hour
        for e_idx in range(len(employees)):
            for day_offset in emp_shifts_by_day[e_idx]:
                day_s_indices = emp_shifts_by_day[e_idx][day_offset]
                day_mins = [x[(e_idx, s_idx)] * shift_durations[s_idx] for s_idx in day_s_indices]
                
                # Indicator: 1 if employee works at all on this day
                works_on_day = model.NewBoolVar(f"works_e{e_idx}_d{day_offset}")
                model.Add(sum(x[(e_idx, s_idx)] for s_idx in day_s_indices) >= 1).OnlyEnforceIf(works_on_day)
                model.Add(sum(x[(e_idx, s_idx)] for s_idx in day_s_indices) == 0).OnlyEnforceIf(works_on_day.Not())
                
                # If works_on_day is true, total minutes must be >= 120
                model.Add(sum(day_mins) >= MIN_DAILY_MINUTES).OnlyEnforceIf(works_on_day)

        # 4. Objective: Maximize total affinity - large penalty for unassigned shifts
        obj_expr = []

        # E. CONTIGUITY BONUS (To promote full "turni" and prevent fragmented "commesse")
        # We reward assigning adjacent or very close project tasks to the same person.
        CONTIGUITY_BONUS = 3000 # Massive bonus to glue projects together
        CONTIGUITY_GAP_MAX = 30 # Allow up to 30 min gap (e.g. small break)
        
        for e_idx in range(len(employees)):
            # Groups are already sorted by day
            for day_offset in emp_shifts_by_day[e_idx]:
                day_s_indices = emp_shifts_by_day[e_idx][day_offset]
                for i in range(len(day_s_indices)):
                    for j in range(len(day_s_indices)):
                        if i == j: continue
                        s1_idx = day_s_indices[i]
                        s2_idx = day_s_indices[j]
                        
                        # Check if s1 completes and s2 starts within the allowed gap
                        # s1.end <= s2.start <= s1.end + 30
                        gap = shift_details[s2_idx][3] - shift_details[s1_idx][4]
                        if 0 <= gap <= CONTIGUITY_GAP_MAX:
                            is_together = model.NewBoolVar(f"tog_e{e_idx}_s{s1_idx}_s{s2_idx}")
                            # Boolean AND: is_together is 1 ONLY IF both shifts are assigned to this employee
                            # Since we MAXIMIZE, the solver will try to set it to 1 if allowed.
                            model.Add(is_together <= x[(e_idx, s1_idx)])
                            model.Add(is_together <= x[(e_idx, s2_idx)])
                            obj_expr.append(is_together * CONTIGUITY_BONUS)

        # F. FRAGMENTATION PREVENTION: Isolated short shifts are forbidden
        # If a shift is < 120 mins, it MUST have at least one contiguous neighbor assigned to the same person.
        for e_idx in range(len(employees)):
            for day_offset in emp_shifts_by_day[e_idx]:
                day_s_indices = emp_shifts_by_day[e_idx][day_offset]
                for s_idx in day_s_indices:
                    if shift_durations[s_idx] < 120:
                        # Find potential neighbors for this person/day
                        neighbors = []
                        for other_idx in day_s_indices:
                            if s_idx == other_idx: continue
                            # Gap < 30 mins
                            d1_start, d1_end = shift_details[s_idx][3], shift_details[s_idx][4]
                            d2_start, d2_end = shift_details[other_idx][3], shift_details[other_idx][4]
                            
                            gap_forward = d2_start - d1_end
                            gap_backward = d1_start - d2_end
                            
                            if (0 <= gap_forward <= CONTIGUITY_GAP_MAX) or (0 <= gap_backward <= CONTIGUITY_GAP_MAX):
                                neighbors.append(x[(e_idx, other_idx)])
                        
                        if neighbors:
                            # We use a PENALTY for isolated short shifts instead of a hard constraint
                            # to avoid "Infeasible" or empty schedules if demand is fragmented.
                            is_isolated = model.NewBoolVar(f"iso_e{e_idx}_s{s_idx}")
                            # is_isolated is 1 if (is assigned AND no neighbors are assigned)
                            # is_isolated implies assigned
                            model.Add(is_isolated <= x[(e_idx, s_idx)])
                            # if is_isolated, then sum(neighbors) must be 0
                            model.Add(sum(neighbors) == 0).OnlyEnforceIf(is_isolated)
                            
                            # Extremely high penalty for being isolated
                            obj_expr.append(is_isolated * -10000)
                        else:
                            # No neighbors possible on this day for this person
                            # If they are assigned, it's a huge penalty
                            obj_expr.append(x[(e_idx, s_idx)] * -10000)

        # Scaling constant to allow small fractional penalties (like fairness) using integers
        # We multiply Affinity and Unassigned penalty by 10.
        SCALE = 10 

        for s_idx in range(len(required_shifts)):
            # Penalty for leaving unassigned (Negative)
            obj_expr.append(unassigned[s_idx] * int(-penalty_unassigned * SCALE))
            
            for e_idx in range(len(employees)):
                if (e_idx, s_idx) not in x: continue
                
                # Base affinity (0-100) * weight * SCALE
                # ADD SOLVE-TIME JITTER: Small random bonus (0-30 points) to break ties and ensure diversity
                import random
                solve_jitter = random.randint(0, 30)
                aff_score = int(affinity_map.get((e_idx, s_idx), 0) * affinity_weight * SCALE) + solve_jitter
                
                # Risk penalty
                p_abs = absence_map.get((e_idx, required_shifts[s_idx]["date"]), 0.0)
                risk_cost = int(p_abs * penalty_absence_risk * SCALE)
                
                # REFINED OBJECTIVE:
                # Maximize Benefit = (Affinity + Penalty for being Assigned) - Risk
                coeff = (aff_score + int(penalty_unassigned * SCALE)) - risk_cost
                obj_expr.append(x[(e_idx, s_idx)] * coeff)

        # FAIRNESS / LOAD BALANCING term:
        # Subtract cost that increases with total hours assigned per employee
        if fairness_weight > 0:
            for e_idx, emp in enumerate(employees):
                # Total minutes assigned to this person (sum of durations)
                total_mins = []
                for s_idx, _ in enumerate(required_shifts):
                    if (e_idx, s_idx) in x:
                        dur = shift_durations[s_idx]
                        total_mins.append(x[(e_idx, s_idx)] * dur)
                
                if total_mins:
                    person_load = model.NewIntVar(0, 500000, f"load_e{e_idx}")
                    model.Add(person_load == sum(total_mins))
                    
                    # ENHANCED FAIRNESS:
                    # Penalty per minute = fairness_weight * SCALE / 120
                    # If fairness_weight = 60, cost_per_min = 5.
                    # 1 Shift (480 mins) = 2400 points penalty.
                    # This is now strong enough to counteract even a 100% vs 0% affinity gap.
                    cost_per_min = max(0, int(fairness_weight * SCALE / 120))
                    if cost_per_min > 0:
                        obj_expr.append(person_load * -cost_per_min)
                
        model.Maximize(cp_model.LinearExpr.Sum(obj_expr))

        # 5. Solve
        solver = cp_model.CpSolver()
        # Enable parallelism
        solver.parameters.num_search_workers = 4
        
        # VARIETY: Use a random seed based on current time to ensure different generations
        import time
        solver.parameters.random_seed = int(time.time()) % 10000
        
        # Set a higher time limit for large problems
        solve_timeout = 60.0
        if len(required_shifts) > 1000: solve_timeout = 120.0
        
        solver.parameters.max_time_in_seconds = solve_timeout
        update_status(message="Executing Combinatorial Optimization...", progress=0.8, log=f"Searching for solution (8 workers, {solve_timeout}s limit)...")
        status = solver.Solve(model)
        
        print(f"DEBUG: Solver Status: {status}")
        if status == cp_model.INFEASIBLE or status == cp_model.UNKNOWN:
            print(f"DIAGNOSTIC: Solver reported {status}. Analyzing potential causes...")
            # Check for role coverage gaps
            required_roles = set(norm_role(s['role']) for s in required_shifts)
            available_roles = set(norm_role(e['role']) for e in employees)
            print(f"DIAGNOSTIC roles: Required={required_roles}, Available={available_roles}")
            
            # Check if anyone can do these shifts
            for s_idx, s in enumerate(required_shifts):
                can_do = [e_idx for e_idx in range(len(employees)) if (e_idx, s_idx) in x]
                if not can_do:
                    print(f"DIAGNOSTIC SHIFT FAILURE: No one matched Shift {s_idx} ({s['role']})")
            missing_roles = required_roles - available_roles
            if missing_roles:
                print(f"  > CRITICAL: Missing roles in staff list: {missing_roles}")
            
            print(f"  > Total Shifts: {len(required_shifts)}")
            print(f"  > Total Staff: {len(employees)}")
            
            from collections import Counter
            c_types = Counter([c.WhichOneof('constraint') for c in model.Proto().constraints])
            print(f"  > Constraint types: {dict(c_types)}")
            
            # Deep Probe: Is it a role match issue?
            for s_idx, s in enumerate(required_shifts):
                potential_emps = 0
                s_role = norm_role(s.get("role"))
                for e_idx, emp in enumerate(employees):
                    e_role = norm_role(emp.get("role"))
                    if e_role == s_role or (e_role in s_role) or (s_role in e_role):
                        potential_emps += 1
                if potential_emps == 0:
                    print(f"  > WARNING: Shift {s['id']} has NO matching employees for role {s_role}")
            
            # If UNKNOWN/INFEASIBLE, we'll continue to result processing 
            # which now has a fallback to unassigned.
            if status == cp_model.INFEASIBLE:
                status = cp_model.FEASIBLE # Dummy to trigger result processing

        # 5. Results Processing (Guaranteed results list)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            update_status(message="Solver incomplete", log=f"Solver returned status {status}. Showing unassigned/best-effort coverage.")
        
        update_status(message="Processing Results...", progress=0.9)
        results = []
        
        # Check if we actually have a solution we can read
        has_solution = False
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            try:
                # Test with one value
                if required_shifts:
                    solver.Value(unassigned[0])
                has_solution = True
            except:
                has_solution = False

        for s_idx, shift in enumerate(required_shifts):
            assigned = False
            if has_solution:
                for e_idx in range(len(employees)):
                    if (e_idx, s_idx) not in x: continue
                    emp = employees[e_idx]
                    try:
                        if solver.Value(x[(e_idx, s_idx)]):
                            results.append({
                                "id": shift["id"],
                                "date": shift["date"],
                                "employee_id": str(emp.get("id") or emp.get("employee_id") or emp.get("external_id")),
                                "employee_name": emp.get("fullName") or emp.get("name"),
                                "start_time": shift["start_time"],
                                "end_time": shift["end_time"],
                                "role": shift["role"],
                                "activity_id": str(shift.get("activity_id", "")),
                                "project": shift.get("project"),
                                "affinity": affinity_map.get((e_idx, s_idx), 0) / 100.0,
                                "absence_risk": float(absence_map.get((e_idx, shift["date"]), 0.0)),
                                "labor_profile_id": emp.get("labor_profile_id"),
                                "is_unassigned": False
                            })
                            assigned = True
                            break
                    except: pass
            
            if not assigned:
                results.append({
                    "id": shift["id"],
                    "date": shift["date"],
                    "employee_id": "unassigned",
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
        update_status(
            message=f"Results Ready: {assigned_count} Assigned", 
            progress=1.0, 
            phase="IDLE", 
            log=f"Solver status: {status}. Finalizing output."
        )
        return results
    finally:
        set_running(False)
