from .base import BaseConstraint
from ortools.sat.python import cp_model
from typing import Dict, Any

class WorkLoadConstraint(BaseConstraint):
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        x = context['x']
        employees = context['employees']
        required_shifts = context['required_shifts']
        shift_details = context['shift_details']
        shift_durations = context['shift_durations']
        policy_service = context['policy_service']

        for e_idx, emp in enumerate(employees):
            max_minutes_weekly = policy_service.get_max_weekly_minutes(emp)
            
            # Group shift indices by (Year, WeekNumber)
            work_by_week = {} 
            for s_idx, _ in enumerate(required_shifts):
                if (e_idx, s_idx) in x:
                    d_obj = shift_details[s_idx][2]
                    yw = d_obj.isocalendar()[:2] 
                    if yw not in work_by_week: work_by_week[yw] = []
                    
                    duration = shift_durations[s_idx]
                    work_by_week[yw].append(x[(e_idx, s_idx)] * duration)
            
            for yw, minutes in work_by_week.items():
                model.Add(sum(minutes) <= max_minutes_weekly)

