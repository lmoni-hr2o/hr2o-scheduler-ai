from datetime import datetime
import numpy as np
from typing import List, Dict, Any, Optional
from utils.datastore_helper import get_db
from google.cloud import datastore
from utils.company_resolver import resolve_environment_to_id

class DemandProfiler:
    """
    Learns high-fidelity staffing patterns (multiple shifts, variable headcount) 
    from historical Period data.
    """
    
    def __init__(self, environment: str):
        self.environment = resolve_environment_to_id(environment) if environment else None
        self.profile = {} # { activity_id: { dow: [ {start, end, qty} ] } }

    def learn_from_periods(self, raw_periods: List[Dict[str, Any]], max_age_days: int = 180, 
                           active_employee_ids: Optional[set] = None, 
                           active_activity_ids: Optional[set] = None):
        from utils.date_utils import parse_date
        from datetime import timedelta, timezone

        # Ensure we have aware datetimes for comparison
        now = datetime.now(timezone.utc)
        
        # Default cutoff for general trends (increased to 3 years to catch older environments)
        cutoff_standard = now - timedelta(days=1095)
        # Extended cutoff for active staff (5 years)
        cutoff_extended = now - timedelta(days=1825)
        
        print(f"DEBUG Profiler: Learning from {len(raw_periods)} periods. ActiveEmp={len(active_employee_ids) if active_employee_ids else 'None'}")

        # 1. Accumulate all historical shifts
        history = {} 
        valid_dates = set()

        for p in raw_periods:
            try:
                # Dotted key lookup helper for flat-nested structures (matching ForecastingService)
                def get_val_robust(obj, key_variants):
                    for kv in key_variants:
                        # 1. Try as direct key (handles flat dotted keys or simple keys)
                        if kv in obj: 
                            val = obj[kv]
                            if isinstance(val, list) and len(val) > 0: return val[0]
                            return val
                        # 2. Try as nested path
                        if "." in kv:
                            parts = kv.split(".")
                            curr = obj
                            found = False
                            for part in parts:
                                # Handle case where intermediate part might be a list
                                if isinstance(curr, list) and len(curr) > 0:
                                    curr = curr[0] # Take first
                                
                                if isinstance(curr, dict) and part in curr:
                                    curr = curr[part]
                                    found = True
                                else:
                                    found = False
                                    break
                            if found:
                                if isinstance(curr, list) and len(curr) > 0: return curr[0]
                                return curr
                    return None

                # A. Employee Extraction
                emp_id = str(get_val_robust(p, ["employeeId", "employmentId", "employees.id", "employment.id", "employment.code"]) or "")
                if (not emp_id or emp_id == "None") and hasattr(p.get("employees"), "key"):
                    emp_id = str(p["employees"].key.id_or_name)
                elif (not emp_id or emp_id == "None") and hasattr(p.get("employment"), "key"):
                    emp_id = str(p["employment"].key.id_or_name)
                
                if not emp_id or emp_id == "None": continue

                # B. Datetime Extraction & Future Outlier Filter
                reg_dt = get_val_robust(p, ["tmentry", "tmregister", "tmRegister", "beginTimePlace.tmregister", "beginTimePlan"])
                if not reg_dt: continue
                if not hasattr(reg_dt, "hour"):
                    reg_dt = parse_date(reg_dt)
                if not reg_dt: continue
                
                # Make aware if naive
                if reg_dt.tzinfo is None: reg_dt = reg_dt.replace(tzinfo=timezone.utc)
                
                # Filter typo dates (future entries)
                if reg_dt > now + timedelta(days=2): continue
                
                # C. Activity Extraction
                act_id = str(get_val_robust(p, ["activityId", "activities.id", "activities.code"]) or "")
                acts = p.get("activities")
                if (not act_id or act_id == "None") and isinstance(acts, list) and len(acts) > 0:
                    a0 = acts[0]
                    act_id = str(a0.get("id") or a0.get("code") or "")
                if (not act_id or act_id == "None") and hasattr(acts, "key") and acts.key:
                    act_id = str(acts.key.id_or_name)

                if not act_id or act_id == "None": continue

                # D. FILTERING LOGIC
                # 1. Activity Filter (Skip legacy/obsolete)
                if active_activity_ids is not None and act_id not in active_activity_ids:
                    continue
                
                # 2. Employee Filter (Learn only from current staff)
                is_active_emp = active_employee_ids is None or emp_id in active_employee_ids
                if not is_active_emp:
                    continue
                
                # 3. Recency Filter (Extended for active, standard for others)
                effective_cutoff = cutoff_extended if is_active_emp else cutoff_standard
                if reg_dt < effective_cutoff:
                    continue
                
                # E. Time Extraction
                dow = str(reg_dt.weekday())
                date_iso = reg_dt.date().isoformat()
                valid_dates.add(date_iso)
                
                tmentry = get_val_robust(p, ["tmentry", "tmregister", "tmRegister", "beginTimePlace.tmregister", "beginTimePlan"])
                tmexit = get_val_robust(p, ["tmexit", "tmRegisterExit", "endTimePlace.tmregister", "endTimePlan", "endTimePlace"])
                
                if not tmentry or not tmexit: continue
                
                def to_hm(t):
                    dt_obj = t
                    if not hasattr(t, "hour"):
                        dt_obj = parse_date(t)
                    if not dt_obj: return "00:00"
                    
                    # Round to nearest 15 minutes
                    minutes = dt_obj.hour * 60 + dt_obj.minute
                    remainder = minutes % 15
                    if remainder >= 8: minutes += (15 - remainder)
                    else: minutes -= remainder
                        
                    h = (minutes // 60) % 24
                    m = minutes % 60
                    return f"{h:02d}:{m:02d}"

                start_hm = to_hm(tmentry)
                end_hm = to_hm(tmexit)

                # Convert to minute-offsets for merging
                h1, m1 = map(int, start_hm.split(':'))
                h2, m2 = map(int, end_hm.split(':'))
                s_min, e_min = h1*60+m1, h2*60+m2
                if e_min < s_min: e_min += 1440

                # F. Role Extraction
                src_role = get_val_robust(p, ["role", "roleId"])
                if not src_role:
                    role_name = "WORKER"
                else:
                    role_name = str(src_role).strip().upper()
                
                # G. Grouping for Merging (emp + date + act + role)
                # To handle multiple commesse/entries within the same session
                merge_key = (emp_id, date_iso, act_id, role_name)
                if merge_key not in sessions: sessions[merge_key] = []
                sessions[merge_key].append([s_min, e_min])

            except Exception: 
                continue

        # 1.4 Post-Processing: Merge fragmented sessions
        # If the same employee has multiple overlapping or contiguous entries for the same activity/role
        # on the same day, we treat them as a single continuous work block.
        # ADDED: 30-min buffer for merging near-contiguous tasks
        MERGE_BUFFER = 30 
        for (emp_id, date_iso, act_id, role_name), intervals in sessions.items():
            if not intervals: continue
            intervals.sort(key=lambda x: x[0])
            
            merged = []
            curr_s, curr_e = intervals[0]
            for i in range(1, len(intervals)):
                nxt_s, nxt_e = intervals[i]
                # Allow 30 mins gap to count as continuous work session
                if nxt_s <= (curr_e + MERGE_BUFFER): 
                    curr_e = max(curr_e, nxt_e)
                else:
                    merged.append((curr_s, curr_e))
                    curr_s, curr_e = nxt_s, nxt_e
            merged.append((curr_s, curr_e))

            # Store in final history for profiling
            reg_dt = datetime.fromisoformat(date_iso)
            dow = str(reg_dt.weekday())
            key = (act_id, dow, role_name)
            if key not in history: history[key] = {}
            if date_iso not in history[key]: history[key][date_iso] = []
            
            for ms, me in merged:
                # Filter out micro-tasks (less than 45 mins) from the LEARNING phase too
                if (me - ms) < 45: continue
                
                # Convert back to HM
                sh, sm = (ms // 60) % 24, ms % 60
                eh, em = (me // 60) % 24, me % 60
                history[key][date_iso].append((f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"))

        # 1.5 Calculate Year Span (Denominator for frequency)
        if valid_dates:
            min_d_iso = min(valid_dates)
            max_d_iso = max(valid_dates)
            min_dt_obj = datetime.fromisoformat(min_d_iso)
            max_dt_obj = datetime.fromisoformat(max_d_iso)
            total_days = (max_dt_obj - min_dt_obj).days + 1
            total_weeks = max(1, total_days / 7.0)
        else:
            total_weeks = 1

        def norm_role(r):
            return str(r or "worker").strip().upper()

        # 2. Extract "Typical" Days for each (act, dow, role)
        final_profile = {}
        
        # Occurrence threshold: 40% (reduced from 50% to be slightly more inclusive but still clean)
        min_occurrence = max(1, total_weeks * 0.40)

        for (act_id, dow, role_name), days_data in history.items():
            # A "Typical Day" is composed of several shifts (slots)
            # Count occurrences of specific (start, end) pairs across all days
            slot_frequencies = {}
            for slots in days_data.values():
                for s in slots:
                    slot_frequencies[s] = slot_frequencies.get(s, 0) + 1
            
            typical_slots = []
            
            # Sort by frequency
            sorted_slots = sorted(slot_frequencies.items(), key=lambda x: x[1], reverse=True)
            
            for (start, end), count in sorted_slots:
                if count >= min_occurrence:
                    # Calculate median quantity for THIS specific slot when it occurs
                    # Median is more robust than MEAN against historical "surge" days
                    daily_qtys = []
                    for slots in days_data.values():
                        q = sum(1 for s in slots if s == (start, end))
                        if q > 0: daily_qtys.append(q)
                    
                    avg_qty = int(np.round(np.median(daily_qtys))) if daily_qtys else 1
                    
                    typical_slots.append({
                        "start_time": start,
                        "end_time": end,
                        "quantity": max(1, avg_qty),
                        "role": norm_role(role_name)
                    })
            
            # MERGE CONTIGUOUS SLOTS (e.g. 08-09 and 09-10 -> 08-10)
            # This is vital when historical data is recorded as small work segments.
            merged_slots = []
            if typical_slots:
                # Sort by start time to detect contiguity
                typical_slots.sort(key=lambda x: x["start_time"])
                
                curr = typical_slots[0]
                for next_s in typical_slots[1:]:
                    # If end of current matches start of next, same role and qty (prob 1 anyway)
                    # We merge them into a single larger block.
                    if next_s["start_time"] == curr["end_time"]:
                        curr["end_time"] = next_s["end_time"]
                        # We use the max quantity if they differ (rare for recurring slots)
                        curr["quantity"] = max(curr["quantity"], next_s["quantity"])
                    else:
                        merged_slots.append(curr)
                        curr = next_s
                merged_slots.append(curr)
                typical_slots = merged_slots

            if typical_slots:
                if act_id not in final_profile: final_profile[act_id] = {}
                final_profile[act_id][dow] = typical_slots

        self.profile = final_profile
        return final_profile

    def save_to_datastore(self):
        """ STRICTLY DISABLED: Read-only mode requested by user. """
        pass
        # No writing allowed to Datastore for any reason.

def get_demand_profile(environment: str) -> Dict[str, Any]:
    """
    Fetches the DemandProfile, with fallback for string-to-numeric environment mapping.
    """
    try:
        from utils.company_resolver import resolve_environment_to_id
        resolved_env = resolve_environment_to_id(environment)
        
        client = get_db().client
        
        # 1. Primary Look up
        key = client.key("DemandProfile", resolved_env)
        entity = client.get(key)
        
        # 2. String-to-Numeric Fallback if not found or empty
        is_empty = not entity or not entity.get("data_json") or entity.get("data_json") == "{}"
        
        if is_empty and not str(resolved_env).isdigit():
            # Try to find a numeric environment mapping
            try:
                # HEURISTIC: OverClean hardcode if needed or general lookup
                if str(resolved_env).upper() == "OVERCLEAN":
                    key_fallback = client.key("DemandProfile", "5629499534213120")
                    entity = client.get(key_fallback)
                else:
                    # Query all DemandProfiles and see if one has this environment as metadata
                    # (A bit expensive, but rare fallback)
                    query = client.query(kind="DemandProfile")
                    query.add_filter("environment", "=", resolved_env) 
                    res = list(query.fetch(limit=1))
                    if res: 
                        entity = res[0]
            except Exception:
                pass

        if entity and "data_json" in entity:
            import json
            return json.loads(entity["data_json"])
    except Exception:
        pass
    return {}
