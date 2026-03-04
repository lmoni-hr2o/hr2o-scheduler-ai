from datetime import datetime, timedelta
from typing import List, Dict, Optional
from services.forecasting_service import ForecastingService
from utils.demand_profiler import get_demand_profile
import psutil
from config import settings

class DemandService:
    def __init__(self, environment: str):
        self.environment = environment
        self.forecaster = ForecastingService(environment)

    def generate_shifts(self, start_date: str, end_date: str, activities: List[dict] = []) -> List[dict]:
        """
        Main entry point for demand generation. 
        Tries ML first, falls back to Demand Profiler, then to smart defaults.
        """
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        try:
            return self._generate_from_ml(start_dt, end_dt, activities)
        except Exception as e:
            print(f"ML Forecasting failed ({e}), using fallback.")
            return self._generate_from_balancer(start_dt, end_dt, activities)

    def _generate_from_ml(self, start_dt: datetime, end_dt: datetime, activities: List[dict]) -> List[dict]:
        active_ids = [str(a.get("id")) for a in activities if a.get("id")]
        predicted_demand = self.forecaster.predict_demand(start_dt, end_dt, activity_ids=active_ids)
        
        if not predicted_demand:
            raise ValueError("No ML predictions available")

        # Memory Guard
        available_mem_gb = psutil.virtual_memory().available / (1024**3)
        memory_limit = max(settings.MIN_MEMORY_LIMIT, int(available_mem_gb * settings.SHIFTS_PER_GB))
        
        if len(predicted_demand) > memory_limit:
            predicted_demand = predicted_demand[:memory_limit]

        shifts = []
        for item in predicted_demand:
            # Chunking logic translated from engine.py
            act_id = str(item["activity_id"])
            date_str = item["date"]
            act_info = next((a for a in activities if str(a.get("id")) == act_id), None)
            role_hint = str(act_info.get("name", "worker")).strip().upper() if act_info else "WORKER"
            
            hours_needed = item["predicted_hours"]
            target_dur = item.get("typical_duration", 6.0)
            typical_start = item.get("typical_start_hour", 8.0)

            remaining = hours_needed
            i = 0
            while remaining >= 2.0:
                block = min(target_dur, remaining)
                if 0 < (remaining - block) < 2.0 and remaining <= 12.0:
                    block = remaining
                
                curr_h = typical_start + ((i % 4) * 0.25)
                start_h, start_m = int(curr_h), int((curr_h - int(curr_h)) * 60)
                end_h, end_m = int(curr_h + block), int(((curr_h + block) - int(curr_h + block)) * 60)
                
                s_time = f"{start_h:02d}:{start_m:02d}"
                e_time = f"{end_h:02d}:{end_m:02d}"
                
                shifts.append({
                    "id": f"ml_{act_id}_{date_str}_{i}_{s_time.replace(':','')}",
                    "date": date_str,
                    "start_time": s_time,
                    "end_time": e_time,
                    "role": role_hint,
                    "activity_id": act_id,
                    "project": act_info.get("project") if act_info else None
                })
                remaining -= block
                i += 1
        return shifts

    def _generate_from_balancer(self, start_dt: datetime, end_dt: datetime, activities: List[dict]) -> List[dict]:
        from utils.demand_profiler import get_demand_profile
        profile = get_demand_profile(self.environment)
        if not profile:
            # Smart defaults: Create 1 default shift per activity (up to 20 activities) per day
            shifts = []
            num_days = (end_dt - start_dt).days + 1
            max_activities = activities[:20] if activities else []
            for d in range(num_days):
                current_date = (start_dt + timedelta(days=d))
                date_str = current_date.date().isoformat()
                for s_idx, act in enumerate(max_activities):
                    act_id = str(act.get("id", "fallback"))
                    shifts.append({
                        "id": f"default_{act_id}_{date_str}_{s_idx}",
                        "date": date_str,
                        "start_time": "08:00",
                        "end_time": "14:00",
                        "role": "WORKER",
                        "activity_id": act_id,
                        "project": act.get("project")
                    })
            return shifts

        shifts = []
        num_days = (end_dt - start_dt).days + 1
        for d in range(num_days):
            current_date = (start_dt + timedelta(days=d))
            date_str = current_date.date().isoformat()
            dow = str(current_date.weekday())
            
            active_ids = {str(a.get("id")) for a in activities if a.get("id")}
            for act_id, dow_patterns in profile.items():
                if active_ids and str(act_id) not in active_ids: continue
                if dow not in dow_patterns: continue
                
                slots = dow_patterns[dow]
                if isinstance(slots, dict): slots = [slots]
                
                act_info = next((a for a in activities if str(a.get("id")) == str(act_id)), None)
                for p_idx, p in enumerate(slots):
                    qty = p.get("quantity", 1)
                    for s_idx in range(qty):
                        shifts.append({
                            "id": f"learned_{act_id}_{date_str}_{p['start_time'].replace(':','')}_slot_{s_idx}",
                            "date": date_str,
                            "start_time": p["start_time"],
                            "end_time": p["end_time"],
                            "role": p.get("role", "worker").upper(),
                            "activity_id": act_id,
                            "project": act_info.get("project") if act_info else None
                        })
        return shifts
