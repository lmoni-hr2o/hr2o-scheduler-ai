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

    def generate_shifts(self, start_date: str, end_date: str, activities: List[dict] = [], employees: List[dict] = []) -> List[dict]:
        """
        Main entry point for demand generation. 
        Tries ML first, falls back to Capacity-based generation.
        """
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        try:
            # We try ML/Profile first if we have enough data
            return self._generate_from_ml(start_dt, end_dt, activities)
        except Exception as e:
            print(f"ML Forecasting failed or disabled ({e}), using capacity-based fallback.")
            return self._generate_from_capacity(start_dt, end_dt, activities, employees)

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
                
                # Stagger shifts: If we need multiple blocks for the same activity on the same day,
                # we prefer spreading them (e.g. 08-12, 12-16) instead of stacking them all at typical_start.
                # This ensures we get both morning and afternoon coverage if demand is high.
                curr_h = typical_start + (i * block)
                
                # Safety wrap: If staggering pushes us past 10PM, we reset and stack with a tiny offset 
                # (to allow concurrent workers if staggering isn't possible anymore)
                if curr_h > 22.0:
                    curr_h = typical_start + ((i % 4) * 0.25)
                
                start_h, start_m = int(curr_h), int((curr_h - int(curr_h)) * 60)
                end_h, end_m = int(curr_h + block), int(((curr_h + block) - int(curr_h + block)) * 60)
                
                # Secondary safety: if end_h > 24, cap it
                if end_h >= 24:
                    end_h, end_m = 23, 59
                
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

    def _generate_from_capacity(self, start_dt: datetime, end_dt: datetime, activities: List[dict], employees: List[dict]) -> List[dict]:
        """
        CAPACITY-BASED LOGIC:
        Ensures every employee has a shift to fill. 
        Infects specific activities into these slots if available.
        """
        num_days = (end_dt - start_dt).days + 1
        num_employees = len(employees) if employees else 1
        
        print(f"DEMAND_SERVICE: Generating for Capacity ({num_employees} emps) over {num_days} days.")
        
        shifts = []
        for d in range(num_days):
            current_date = (start_dt + timedelta(days=d))
            date_str = current_date.date().isoformat()
            
            # For each active employee, we want to see a block on the grid
            for e_idx in range(num_employees):
                # Distribute activities if we have them
                # e.g. Emp 0 gets Act 0, Emp 1 gets Act 1... Emp 11 gets nothing (generic)
                act_idx = e_idx
                current_act = activities[act_idx] if activities and act_idx < len(activities) else None
                
                act_id = str(current_act.get("id")) if current_act else "generic"
                act_name = current_act.get("name", "Lavoro Normale") if current_act else "Lavoro Normale"
                
                # Alternate between morning and afternoon shifts to avoid pure morning concentration
                is_afternoon = (e_idx % 2 != 0)
                s_time = "14:00" if is_afternoon else "08:00"
                e_time = "20:00" if is_afternoon else "14:00"
                
                shifts.append({
                    "id": f"cap_{date_str}_{e_idx}",
                    "date": date_str,
                    "start_time": s_time,
                    "end_time": e_time,
                    "role": "WORKER",
                    "activity_id": act_id,
                    "activity_name": act_name,
                    "project": current_act.get("project") if current_act else None
                })
        
        print(f"DEMAND_SERVICE: Capacity shifts generated: {len(shifts)}")
        return shifts
