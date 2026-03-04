class PlannerError(Exception):
    """Base category for all planner errors."""
    def __init__(self, message: str, detail: str = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

class InfeasibleError(PlannerError):
    """Raised when the CP-SAT model cannot find any solution."""
    pass

class MemoryLimitError(PlannerError):
    """Raised when the problem size exceeds safe memory limits."""
    pass

class DataIntegrityError(PlannerError):
    """Raised when input data is missing or corrupted."""
    pass
