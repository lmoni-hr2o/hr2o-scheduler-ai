from .base import BaseConstraint
from ortools.sat.python import cp_model
from typing import Dict, Any

class CoverageConstraint(BaseConstraint):
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        x = context['x']
        unassigned = context['unassigned']
        employees = context['employees']
        required_shifts = context['required_shifts']

        for s_idx, shift in enumerate(required_shifts):
            eligible_vars = [x[(e_idx, s_idx)] for e_idx in range(len(employees)) if (e_idx, s_idx) in x]
            model.Add(sum(eligible_vars) + unassigned[s_idx] == 1)
