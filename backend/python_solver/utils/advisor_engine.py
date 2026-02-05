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

        # 3. Feasibility Analysis
        gap = total_contract_hours - total_demand_hours
        utilization = (total_demand_hours / total_contract_hours * 100) if total_contract_hours > 0 else 0
        
        summary = f"Analisi Tecnica: Disponibilità {total_contract_hours:.1f}h vs Carico Stimato {total_demand_hours:.1f}h. "
        if utilization > 95:
            summary += "Attenzione: saturazione altissima (>95%). Rischio elevato di turni scoperti."
        elif utilization < 60:
            summary += "Bassa saturazione (<60%). Possibile eccesso di personale per questa settimana."
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

        # D. Technical Check (DOW check)
        # If demand is 0, we should warn
        if total_demand_hours == 0:
            suggestions.append({
                "title": "Verifica Dati Sorgente",
                "description": "Non ho rilevato storico per questo periodo. Assicurati che le commesse siano state sincronizzate correttamente o carica uno storico precedente.",
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
