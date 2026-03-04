from .base import BaseConstraint
from ortools.sat.python import cp_model
from typing import Dict, Any

class OverlapConstraint(BaseConstraint):
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        x = context['x']
        employees = context['employees']
        required_shifts = context['required_shifts']
        shift_details = context['shift_details']
        shift_durations = context['shift_durations']

        for e_idx, emp in enumerate(employees):
            intervals = []
            for s_idx, shift in enumerate(required_shifts):
                if (e_idx, s_idx) not in x: continue
                
                presence = x[(e_idx, s_idx)]
                iv = model.NewOptionalIntervalVar(
                    shift_details[s_idx][3], 
                    shift_durations[s_idx], 
                    shift_details[s_idx][4], 
                    presence, 
                    f'ival_e{e_idx}_s{s_idx}'
                )
                intervals.append(iv)
            
            if intervals:
                model.AddNoOverlap(intervals)
