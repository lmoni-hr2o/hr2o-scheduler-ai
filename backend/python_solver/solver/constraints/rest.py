from .base import BaseConstraint
from ortools.sat.python import cp_model
from typing import Dict, Any
from config import settings

class RestConstraint(BaseConstraint):
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        x = context['x']
        employees = context['employees']
        required_shifts = context['required_shifts']
        shift_details = context['shift_details']
        
        rest_period = settings.REST_PERIOD_MINUTES

        for e_idx in range(len(employees)):
            # Sort viable shifts by absolute start time
            e_viable_indices = sorted([s_idx for s_idx in range(len(required_shifts)) if (e_idx, s_idx) in x], 
                                     key=lambda idx: shift_details[idx][3])
            
            for i in range(len(e_viable_indices)):
                s1_idx = e_viable_indices[i]
                for j in range(i + 1, len(e_viable_indices)):
                    s2_idx = e_viable_indices[j]
                    # Since sorted, if s2 starts > 24h after s1 ends, we can stop checking for s1
                    if shift_details[s2_idx][3] > shift_details[s1_idx][4] + 1440:
                        break
                    
                    # If the gap between end of s1 and start of s2 is < rest_period, they cannot both be assigned
                    if shift_details[s2_idx][3] < shift_details[s1_idx][4] + rest_period:
                        model.Add(x[(e_idx, s1_idx)] + x[(e_idx, s2_idx)] <= 1)
