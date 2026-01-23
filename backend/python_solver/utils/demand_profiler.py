from datetime import datetime
import numpy as np
from typing import List, Dict, Any
from utils.datastore_helper import get_db
from google.cloud import datastore

class DemandProfiler:
    """
    Learns high-fidelity staffing patterns (multiple shifts, variable headcount) 
    from historical Period data.
    """
    
    def __init__(self, environment: str):
        self.environment = environment
        self.profile = {} # { activity_id: { dow: [ {start, end, qty} ] } }

    def learn_from_periods(self, raw_periods: List[Dict[str, Any]]):
        from utils.date_utils import parse_date

        # 1. Accumulate all historical shifts
        # key: (act_id, dow) -> list of days [ {date: iso, slots: [ (start, end) ] } ]
        history = {} 

        for p in raw_periods:
            try:
                act_data = p.get("activities", {})
                act_id = str(p.get("_entity_id_activity", "")) or str(act_data.get("id", ""))
                if not act_id or act_id == "None": continue
                
                tmregister = p.get("tmregister")
                reg_dt = parse_date(tmregister)
                if not reg_dt: continue
                
                dow = str(reg_dt.weekday())
                date_iso = reg_dt.date().isoformat()
                
                tmentry = p.get("tmentry")
                tmexit = p.get("tmexit")
                if not tmentry or not tmexit: continue
                
                def to_hm(t):
                    if hasattr(t, 'hour'): return f"{t.hour:02d}:{t.minute:02d}"
                    pts = parse_date(t)
                    if pts: return f"{pts.hour:02d}:{pts.minute:02d}"
                    return str(t).split('T')[-1][:5]

                start_hm = to_hm(tmentry)
                end_hm = to_hm(tmexit)
                
                key = (act_id, dow)
                if key not in history: history[key] = {}
                if date_iso not in history[key]: history[key][date_iso] = []
                
                history[key][date_iso].append((start_hm, end_hm))
            except: continue

        # 2. Extract "Typical" Days for each (act, dow)
        final_profile = {}
        
        for (act_id, dow), days_data in history.items():
            # A "Typical Day" is composed of several shifts (slots)
            # We want to find the most common set of slots.
            
            # Count occurrences of specific (start, end) pairs across all days
            slot_frequencies = {}
            for slots in days_data.values():
                for s in slots:
                    slot_frequencies[s] = slot_frequencies.get(s, 0) + 1
            
            # Only keep slots that appear in at least 20% of the historical days for this DOW
            min_occurrence = max(1, len(days_data) * 0.2)
            typical_slots = []
            
            # Sort by frequency
            sorted_slots = sorted(slot_frequencies.items(), key=lambda x: x[1], reverse=True)
            
            for (start, end), count in sorted_slots:
                if count >= min_occurrence:
                    # Calculate average quantity for THIS specific slot when it occurs
                    daily_qtys = []
                    for slots in days_data.values():
                        q = sum(1 for s in slots if s == (start, end))
                        if q > 0: daily_qtys.append(q)
                    
                    avg_qty = int(np.round(np.mean(daily_qtys))) if daily_qtys else 1
                    
                    typical_slots.append({
                        "start_time": start,
                        "end_time": end,
                        "quantity": max(1, avg_qty)
                    })
            
            if typical_slots:
                if act_id not in final_profile: final_profile[act_id] = {}
                final_profile[act_id][dow] = typical_slots

        self.profile = final_profile
        return final_profile

    def save_to_datastore(self):
        client = get_db().client
        key = client.key("DemandProfile", self.environment)
        # Use JSON dump for stability
        import json
        entity = datastore.Entity(key=key, exclude_from_indexes=['data_json'])
        entity.update({
            "environment": self.environment,
            "data_json": json.dumps(self.profile),
            "last_updated": datetime.now()
        })
        client.put(entity)

def get_demand_profile(environment: str) -> Dict[str, Any]:
    try:
        client = get_db().client
        key = client.key("DemandProfile", environment)
        entity = client.get(key)
        if entity and "data_json" in entity:
            import json
            return json.loads(entity["data_json"])
    except: pass
    return {}
