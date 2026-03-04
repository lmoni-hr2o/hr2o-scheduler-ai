from typing import List, Dict, Any
from ortools.sat.python import cp_model
from .base import BaseConstraint
from .rest import RestConstraint
from .workload import WorkLoadConstraint
from .overlap import OverlapConstraint
from .coverage import CoverageConstraint
from .contiguity import ContiguityConstraint

class ConstraintFactory:
    @staticmethod
    def get_default_constraints() -> List[BaseConstraint]:
        return [
            CoverageConstraint(),
            OverlapConstraint(),
            RestConstraint(),
            WorkLoadConstraint(),
            ContiguityConstraint()
        ]

    def apply_all(self, model: cp_model.CpModel, context: Dict[str, Any], constraints: List[BaseConstraint] = None):
        if constraints is None:
            constraints = self.get_default_constraints()
        
        for constraint in constraints:
            constraint.add_to_model(model, context)
