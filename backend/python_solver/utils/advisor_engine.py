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
        
        # 2. Demand Calculation (from Profile)
        total_demand_hours = 0
        if start_date and end_date:
            try:
                s_dt = datetime.fromisoformat(start_date)
                e_dt = datetime.fromisoformat(end_date)
                num_days = (e_dt - s_dt).days + 1
                
                for d in range(num_days):
                    curr_dt = s_dt + timedelta(days=d)
                    dow = str(curr_dt.weekday())
                    
                    # Correct iteration for { act_id: { dow: [slots] } }
                    for act_id, dow_patterns in demand_profile.items():
                        if dow in dow_patterns:
                            slots = dow_patterns[dow]
                            if isinstance(slots, list):
                                for slot in slots:
                                    try:
                                        h1, m1 = map(int, slot["start_time"].split(':'))
                                        h2, m2 = map(int, slot["end_time"].split(':'))
                                        dur = (h2*60+m2) - (h1*60+m1)
                                        if dur < 0: dur += 1440
                                        total_demand_hours += (dur / 60.0) * slot.get("quantity", 1)
                                    except: pass
                            elif isinstance(slots, (int, float)):
                                total_demand_hours += slots
            except Exception as e:
                print(f"AdvisorEngine demand error: {e}")

        # 2b. Contractual Demand Calculation (from Activities list in request)
        total_contractual_hours = 0
        if start_date and end_date and activities:
            try:
                s_dt = datetime.fromisoformat(start_date)
                e_dt = datetime.fromisoformat(end_date)
                num_days = (e_dt - s_dt).days + 1
                
                for act in activities:
                    hh_sched = act.get("hhSchedule") # Total weekly minutes
                    daily_low = act.get("dailySchedule") # List of minute/hour settings
                    weekly_dow = act.get("weeklySchedule") # List of active DOWs [0, 1...]
                    
                    if daily_low and isinstance(daily_low, list):
                        # Use daily patterns across the period
                        for d in range(num_days):
                            curr_dt = s_dt + timedelta(days=d)
                            dow_idx = curr_dt.weekday()
                            if dow_idx < len(daily_low):
                                entry = daily_low[dow_idx]
                                if isinstance(entry, dict):
                                    mins = entry.get("durationTime") or 0
                                    # If durationTime is missing, maybe it's hhSchedule / days
                                    total_contractual_hours += (float(mins) / 60.0)
                                elif isinstance(entry, (int, float)):
                                    total_contractual_hours += (float(entry) / 60.0)
                    elif hh_sched:
                        # Fallback to spreading hhSchedule over the period
                        # 960 min / week = 16h / week
                        total_contractual_hours += (float(hh_sched) / 60.0) * (num_days / 7.0)
            except Exception as e_c:
                print(f"AdvisorEngine contractual demand error: {e_c}")

        # Final Demand = Max(Historical Profile, Contractual definition)
        original_learned_demand = total_demand_hours
        total_demand_hours = max(total_demand_hours, total_contractual_hours)
        
        # 3. Feasibility Analysis
        gap = total_contract_hours - total_demand_hours
        utilization = (total_demand_hours / total_contract_hours * 100) if total_contract_hours > 0 else 0
        
        summary = f"Analisi Tecnica: Disponibilità {total_contract_hours:.1f}h vs Carico Stimato {total_demand_hours:.1f}h. "
        if total_demand_hours > 0 and original_learned_demand == 0:
            summary += "(Basato su fabbisogni contrattuali commesse) "

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
        elif original_learned_demand == 0:
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
