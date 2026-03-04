import os
from pydantic import Field
from pydantic_settings import BaseSettings

class SolverConfig(BaseSettings):
    # Coverage & Objective Weights
    AFFINITY_WEIGHT: float = 1.0
    PENALTY_UNASSIGNED: int = 500
    PENALTY_ABSENCE_RISK: int = 200
    FAIRNESS_WEIGHT: float = 80.0
    
    # Technical Constraints
    REST_PERIOD_MINUTES: int = 660  # 11 hours
    MIN_DAILY_MINUTES: int = 60    # 1 hour
    MAX_WEEKLY_HOURS_DEFAULT: float = 40.0
    
    # Bonuses & Penalties
    CONTIGUITY_BONUS: int = 3000
    CONTIGUITY_GAP_MAX_MINUTES: int = 30
    ISOLATION_PENALTY: int = -10000
    SHORT_SHIFT_THRESHOLD_MINUTES: int = 120
    
    # System Scalability
    SCALE_FACTOR: int = 100
    SOLVE_TIMEOUT_SECONDS: float = 60.0
    SOLVE_TIMEOUT_LARGE_SECONDS: float = 120.0
    LARGE_PROBLEM_THRESHOLD: int = 1000
    
    # Memory Management
    SHIFTS_PER_GB: int = 1500
    MIN_MEMORY_LIMIT: int = 1000
    OOM_RISK_THRESHOLD: int = 1000000 # employees * shifts

    class Config:
        env_prefix = "PLANNER_"

# Global instance
settings = SolverConfig()
