from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum

class PositionDetectionSystem(str, Enum):
    manual = "manual"
    local = "local"
    net = "net"
    mobile = "mobile"
    gps = "gps"
    beacon = "beacon"

class TimeDetectionSystem(str, Enum):
    manual = "manual"
    local = "local"
    ntp = "ntp"
    mobile = "mobile"
    gps = "gps"

class TimePlace(BaseModel):
    time: datetime
    place_id: str
    detection_system: Optional[PositionDetectionSystem] = PositionDetectionSystem.manual

class Period(BaseModel):
    id: Optional[str] = None
    environment: str
    tmregister: Optional[datetime] = Field(default_factory=datetime.now)
    allDay: bool = True
    partialDay: Optional[str] = "G" # G=ALL, P=Pomeriggio, M=Mattino
    
    # Planning
    beginTimePlan: Optional[datetime] = None
    endTimePlan: Optional[datetime] = None
    
    # Place (Time + Location)
    beginTimePlace: Optional[TimePlace] = None
    endTimePlace: Optional[TimePlace] = None
    
    # Calculation
    beginTimeCalc: Optional[datetime] = None
    endTimeCalc: Optional[datetime] = None
    
    # Coordinates
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    
    positionDetectionSystem: PositionDetectionSystem = PositionDetectionSystem.manual
    timeDetectionSystem: TimeDetectionSystem = TimeDetectionSystem.manual
    logs: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

class Activity(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    environment: str = ""
    
    # Details
    customer_address: Optional[str] = None
    project_id: Optional[str] = None
    note: Optional[str] = None
    typeActivity: Optional[str] = None
    operations: Optional[List[Dict[str, Any]]] = None # Keep for detailed task analysis
    
    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)

class LaborProfile(BaseModel):
    id: Optional[str] = None
    name: str # e.g. "Part-Time 20h", "Full-Time Standard"
    company_id: str # Owner
    
    # Constraints
    max_weekly_hours: float = 40.0
    max_daily_hours: float = 8.0
    max_consecutive_days: int = 6
    min_rest_hours: float = 11.0
    
    # Flags
    is_default: bool = False
    last_updated: datetime = Field(default_factory=datetime.now)

class Employment(BaseModel):
    id: str
    name: str = "Unknown Company"
    fullName: str = "Unknown Employee"
    role: str = "worker"
    environment: str = ""
    
    # Normalized Fields
    address: Optional[str] = None
    city: Optional[str] = None
    bornDate: Optional[str] = None
    dtHired: Optional[str] = None
    dtDismissed: Optional[str] = None
    
    # Contract Details
    contract_type: Optional[str] = None # e.g. "Full Time", "Part Time"
    contract_hours: Optional[float] = None
    qualification: Optional[str] = None
    
    # System Flags
    has_history: bool = False
    labor_profile_id: Optional[str] = None
    
    # Learned Attributes (for Neural Scorer)
    project_ids: List[str] = Field(default_factory=list)
    customer_keywords: List[str] = Field(default_factory=list)

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)

class AgentRequest(BaseModel):
    environment: str
    timestamp: int
    payload: dict # Flexible payload depending on action

class AlgorithmConfig(BaseModel):
    environment: str = "default"
    affinity_weight: float = 1.0
    penalty_unassigned: float = 100.0
    max_hours_weekly: float = 40.0
    min_rest_hours: float = 11.0
    penalty_absence_risk: float = 200.0
    fairness_weight: float = 50.0  # Weight for load balancing (fairness)
    enable_historical_comparison: bool = True
    last_updated: datetime = Field(default_factory=datetime.now)

class DataMapping(BaseModel):
    environment: str
    mappings: Dict[str, List[str]] # feature_id -> list of raw field paths
    last_updated: datetime = Field(default_factory=datetime.now)
