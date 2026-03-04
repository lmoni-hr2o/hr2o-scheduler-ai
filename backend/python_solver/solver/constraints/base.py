from abc import ABC, abstractmethod
from ortools.sat.python import cp_model
from typing import List, Dict, Any

class BaseConstraint(ABC):
    @abstractmethod
    def add_to_model(self, model: cp_model.CpModel, context: Dict[str, Any]):
        """
        Adds the constraint to the CP-SAT model.
        context should contain:
        - x: dict of variables (e_idx, s_idx) -> BoolVar
        - employees: list
        - required_shifts: list
        - shift_details: list
        - shift_durations: list
        - emp_shifts_by_day: dict
        - ... other model state ...
        """
        pass
