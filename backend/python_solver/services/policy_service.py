from typing import List, Dict, Optional
from datetime import datetime
from config import settings

class PolicyService:
    def __init__(self, labor_profiles: Dict[str, dict]):
        self.labor_profiles = labor_profiles

    def get_max_weekly_minutes(self, emp: dict) -> int:
        profile_id = emp.get("labor_profile_id")
        if profile_id and profile_id in self.labor_profiles:
            max_hours = self.labor_profiles[profile_id].get("max_weekly_hours", settings.MAX_WEEKLY_HOURS_DEFAULT)
        else:
            max_hours = settings.MAX_WEEKLY_HOURS_DEFAULT
        return int(max_hours * 60)

    def get_min_rest_minutes(self, emp: dict) -> int:
        profile_id = emp.get("labor_profile_id")
        if profile_id and profile_id in self.labor_profiles:
            return int(self.labor_profiles[profile_id].get("min_rest_hours", 11.0) * 60)
        return settings.REST_PERIOD_MINUTES
