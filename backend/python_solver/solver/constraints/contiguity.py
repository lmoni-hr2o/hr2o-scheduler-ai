from .base import BaseConstraint
from ortools.sat.python import cp_model
from typing import Dict, Any
from config import settings

class ContiguityConstraint(BaseConstraint):
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        x = context['x']
        employees = context['employees']
        shift_details = context['shift_details']
        emp_shifts_by_day = context['emp_shifts_by_day']
        shift_durations = context['shift_durations']
        obj_expr = context['obj_expr']

        bonus = settings.CONTIGUITY_BONUS
        gap_max = settings.CONTIGUITY_GAP_MAX_MINUTES
        short_threshold = settings.SHORT_SHIFT_THRESHOLD_MINUTES
        penalty = settings.ISOLATION_PENALTY

        for e_idx in range(len(employees)):
            for day_offset, day_s_indices in emp_shifts_by_day[e_idx].items():
                # 1. Contiguity Bonus
                for i in range(len(day_s_indices)):
                    for j in range(len(day_s_indices)):
                        if i == j: continue
                        s1_idx, s2_idx = day_s_indices[i], day_s_indices[j]
                        gap = shift_details[s2_idx][3] - shift_details[s1_idx][4]
                        if 0 <= gap <= gap_max:
                            is_together = model.NewBoolVar(f"tog_e{e_idx}_s{s1_idx}_s{s2_idx}")
                            model.Add(is_together <= x[(e_idx, s1_idx)])
                            model.Add(is_together <= x[(e_idx, s2_idx)])
                            obj_expr.append(is_together * bonus)

                # 2. Fragmentation Prevention (Short shifts must have a neighbor)
                for s_idx in day_s_indices:
                    if shift_durations[s_idx] < short_threshold:
                        neighbors = []
                        for other_idx in day_s_indices:
                            if s_idx == other_idx: continue
                            d1_start, d1_end = shift_details[s_idx][3], shift_details[s_idx][4]
                            d2_start, d2_end = shift_details[other_idx][3], shift_details[other_idx][4]
                            if (0 <= d2_start - d1_end <= gap_max) or (0 <= d1_start - d2_end <= gap_max):
                                neighbors.append(x[(e_idx, other_idx)])
                        
                        if neighbors:
                            is_isolated = model.NewBoolVar(f"iso_e{e_idx}_s{s_idx}")
                            model.Add(is_isolated <= x[(e_idx, s_idx)])
                            model.Add(sum(neighbors) == 0).OnlyEnforceIf(is_isolated)
                            obj_expr.append(is_isolated * penalty)
                        else:
                            obj_expr.append(x[(e_idx, s_idx)] * penalty)
