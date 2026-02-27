import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

class AdvisorEngine:
    """
    Internal 'AI Motor' for deterministic pre-check analysis.
    Focuses on capacity, demand balance, and parameter optimization.
    """

    @staticmethod
    def analyze(environment: str, employees: List[Dict[str, Any]], activities: List[Dict[str, Any]], 
                config: Dict[str, Any], start_date: str, end_date: str, demand_profile: Dict[str, Any]) -> Dict[str, Any]:
        
        # 1. Supply Calculation (Contract Hours)
        total_contract_hours = sum(e.get('contract_hours') or 40.0 for e in employees)
        employee_count = len(employees)
        
        # 2. Demand Calculation
        total_demand_hours = 0
        matched_from_profile = 0 
        
        if start_date and end_date:
            try:
                s_dt = datetime.fromisoformat(start_date)
                e_dt = datetime.fromisoformat(end_date)
                num_days = (e_dt - s_dt).days + 1
                
                # A. Prepare request identifiers for matching
                # Deduplicate activities by ID to avoid inflated demand
                seen_act_ids = set()
                unique_req_activities = []
                active_keys = set()
                
                for a in activities:
                    aid = str(a.get("id") or a.get("activityId") or "")
                    code = str(a.get("code") or "")
                    name = str(a.get("name") or "").upper().strip()
                    
                    if aid and aid not in seen_act_ids:
                        seen_act_ids.add(aid)
                        unique_req_activities.append(a)
                        
                    if aid: active_keys.add(aid)
                    if code: active_keys.add(code)
                    if name: active_keys.add(name)

                # B. Map Profile Keys to Request Activities
                profile_to_req_map = {}
                for prof_id in demand_profile.keys():
                    if str(prof_id) in active_keys:
                        profile_to_req_map[prof_id] = prof_id
                
                # C. Calculate Historical Demand (Deduplicated by Time Overlap)
                # Instead of summing all slots, we aggregate them per day and role to handle multi-project saturation correctly.
                # If multiple activities happen at the same time for the same role, they likely represent the same person's labor.
                daily_role_intervals = {} # (day_str, role) -> [ (start_min, end_min) ]
                
                for prof_id, matched_val in profile_to_req_map.items():
                    dow_patterns = demand_profile.get(prof_id, {})
                    matched_from_profile += 1
                    
                    for d in range(num_days):
                        curr_dt = s_dt + timedelta(days=d)
                        date_str = curr_dt.date().isoformat()
                        dow = str(curr_dt.weekday())
                        
                        if dow in dow_patterns:
                            slots = dow_patterns[dow]
                            if isinstance(slots, list):
                                for slot in slots:
                                    try:
                                        role = slot.get("role", "WORKER").upper()
                                        h1, m1 = map(int, slot["start_time"].split(':'))
                                        h2, m2 = map(int, slot["end_time"].split(':'))
                                        start_min = h1 * 60 + m1
                                        end_min = h2 * 60 + m2
                                        if end_min < start_min: end_min += 1440
                                        
                                        # Quantity Handling: if qty > 1, we still count multiple people.
                                        # To simplify: we add the interval QTY times.
                                        key = (date_str, role)
                                        if key not in daily_role_intervals: daily_role_intervals[key] = []
                                        qty = max(1, int(slot.get("quantity", 1)))
                                        for _ in range(qty):
                                            daily_role_intervals[key].append([start_min, end_min])
                                    except Exception: pass
                
                # Deduplicate and Sum
                total_historical_hours = 0
                for (date_str, role), intervals in daily_role_intervals.items():
                    # Merge overlapping intervals for the same role/day
                    # Sorting by start time
                    intervals.sort(key=lambda x: x[0])
                    if not intervals: continue
                    
                    merged = []
                    curr_start, curr_end = intervals[0]
                    
                    for i in range(1, len(intervals)):
                        next_start, next_end = intervals[i]
                        if next_start < curr_end: # Overlap detected
                            curr_end = max(curr_end, next_end)
                        else:
                            merged.append(curr_end - curr_start)
                            curr_start, curr_end = next_start, next_end
                    merged.append(curr_end - curr_start)
                    
                    total_historical_hours += sum(merged) / 60.0

                # D. Calculate Contractual Demand (only for activities NOT covered by history)
                total_contractual_hours = 0
                historical_covered_ids = {str(req_id) for prof_id, req_id in profile_to_req_map.items() if req_id != "FALLBACK"}
                
                for act in unique_req_activities:
                    aid = str(act.get("id") or act.get("activityId") or "")
                    if aid in historical_covered_ids:
                        continue # Already counted via history
                    
                    # Contractual estimate for this NEW or UNPROFILED activity
                    # We must be careful not to inflate this if hours are not really required.
                    hh_sched = act.get("hhSchedule") 
                    daily_low = act.get("dailySchedule")
                    
                    act_contract_hours = 0
                    if daily_low and isinstance(daily_low, list):
                        # Use daily patterns if available
                        for d in range(num_days):
                            curr_dt = s_dt + timedelta(days=d)
                            dow_idx = curr_dt.weekday()
                            if dow_idx < len(daily_low):
                                entry = daily_low[dow_idx]
                                try:
                                    if isinstance(entry, dict):
                                        val = float(entry.get("durationTime") or 0)
                                        if val > 1440: val = 480 # Cap abnormal values (max 8h/day per act)
                                        act_contract_hours += (val / 60.0)
                                    elif isinstance(entry, (int, float)):
                                        val = float(entry)
                                        if val > 1440: val = 480
                                        act_contract_hours += (val / 60.0)
                                except Exception: pass
                    elif hh_sched:
                        # Weekly schedule fallback
                        try:
                            val = float(hh_sched)
                            # Cap abnormal weekly values (max 40h per activity)
                            if val > 2400: val = 2400
                            act_contract_hours = (val / 60.0) * (num_days / 7.0)
                        except Exception: pass
                    
                    # SAFETY CAP: an unprofiled activity cannot realistically demand 5000h in a week
                    # Unless it's a massive site, but here we cap it to a reasonable maximum per-activity
                    # to avoid the "GIGA-SATURATION" bug.
                    if act_contract_hours > 168: # More than 1 person 24/7? Unlikely for a single unprofiled act
                         act_contract_hours = 40.0 

                    total_contractual_hours += act_contract_hours

                # Final Demand
                # SIGNIFICANT CHANGE: If we have historical demand, we treat unprofiled contractual demand 
                # as "noise" or "optional tasks" and cap it heavily to avoid the 5000h spike.
                if total_historical_hours > 0:
                    # If we have history, unprofiled activities contribute very little 
                    # (only as a 'safety' placeholder)
                    total_demand_hours = total_historical_hours + min(total_contractual_hours, 10.0)
                else:
                    # Full fallback if absolutely no history
                    total_demand_hours = total_contractual_hours

                print(f"DEBUG Advisor: Hist={total_historical_hours:.1f}h, Contractual(New)={total_contractual_hours:.1f}h. Matched={matched_from_profile}")

            except Exception as e:
                print(f"AdvisorEngine demand error: {e}")
                import traceback
                traceback.print_exc()

        
        # 3. Feasibility Analysis
        gap = total_contract_hours - total_demand_hours
        utilization = (total_demand_hours / total_contract_hours * 100) if total_contract_hours > 0 else 0
        
        summary = f"Analisi Tecnica: Disponibilità {total_contract_hours:.1f}h vs Carico Totale {total_demand_hours:.1f}h "
        summary += f"(Storico: {total_historical_hours:.1f}h, Stimato/Contrattuale: {total_contractual_hours:.1f}h). "

        if utilization > 95:
            summary += "Attenzione: saturazione altissima (>95%). Rischio elevato di turni scoperti."
        elif utilization < 60:
            summary += f"Bassa saturazione ({utilization:.1f}%). Possibile eccesso di personale per questa settimana."
        else:
            summary += f"Saturazione ottimale ({utilization:.1f}%). Lo scheduling dovrebbe essere fluido."

        # 4. Suggestions Generation
        suggestions = []
        
        # A. Fairness Suggestion
        cur_fairness = config.get('fairness_weight', 50.0)
        if employee_count > 15 and cur_fairness < 100:
            suggestions.append({
                "title": "Ottimizzazione Bilanciamento (Fairness)",
                "description": f"Hai {employee_count} dipendenti. Aumentare la Fairness a 150 aiuterà a distribuire il carico in modo più equo, evitando burnout.",
                "type": "update_config",
                "payload": {"fairness_weight": 150.0}
            })
        
        # B. Affinity Suggestion
        cur_affinity = config.get('affinity_weight', 1.0)
        if cur_affinity < 1.0:
            suggestions.append({
                "title": "Aumento Stabilità (Affinity)",
                "description": "Il peso dell'affinità è basso. Alzalo a 2.0 per forzare l'IA a rispettare maggiormente le abitudini storiche dei dipendenti.",
                "type": "update_config",
                "payload": {"affinity_weight": 2.0}
            })

        # C. Penalty Unassigned
        if utilization > 90:
            suggestions.append({
                "title": "Priorità Copertura Totale",
                "description": "La saturazione è alta. Aumentare la penale per turni non assegnati a 500 costringerà il motore a coprire ogni buco possibile.",
                "type": "update_config",
                "payload": {"penalty_unassigned": 500.0}
            })

        # Data Quality Warnings
        if total_demand_hours == 0:
            suggestions.append({
                "title": "Verifica Dati Sorgente",
                "description": "Non ho rilevato storico per questo periodo. Assicurati che le commesse siano state sincronizzate correttamente o carica uno storico precedente.",
                "type": "info"
            })
        elif total_historical_hours == 0:
            suggestions.append({
                "title": "Stima Contrattuale",
                "description": "L'analisi si basa sui dati teorici delle commesse perché non ho trovato storico registrato.",
                "type": "info"
            })

        return {
            "summary": summary,
            "suggestions": suggestions,
            "stats": {
                "supply": total_contract_hours,
                "demand": total_demand_hours,
                "utilization": utilization
            }
        }
