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
    role_required: str = "worker" # Fallback if host API doesn't provide it
    environment: str = "" # Injected by router
    
    # Additional fields from real API
    project: Optional[Dict[str, Any]] = None
    customer_address: Optional[str] = None
    code: Optional[str] = None
    note: Optional[str] = None
    typeActivity: Optional[str] = None
    dtEnd: Optional[str] = None
    type: Optional[str] = None
    productivityType: Optional[str] = None
    operations: Optional[List[Dict[str, Any]]] = None
    selectVehicleRequired: bool = False

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)

class Employment(BaseModel):
    id: str
    name: str = "Unknown Company" # Now represents Company Name
    fullName: str = "Unknown Employee" # Now represents Person Name
    role: str = "worker"
    environment: str = ""
    preferences: Optional[List[float]] = Field(default_factory=list)
    
    # Additional fields from real API
    company: Optional[Dict[str, Any]] = None
    person: Optional[Dict[str, Any]] = None
    address: Optional[str] = None
    city: Optional[str] = None
    bornDate: Optional[str] = None
    dtHired: Optional[str] = None
    dtDismissed: Optional[str] = None
    badge: Optional[Dict[str, Any]] = None
    has_history: bool = False # Track if worker has real periods/activities
    project_ids: List[str] = Field(default_factory=list) # Historical projects worked on
    customer_keywords: List[str] = Field(default_factory=list) # Familiar customers (address/name)

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)
    
    @field_validator('fullName', mode='before')
    @classmethod
    def extract_full_name(cls, v: Any, info) -> str:
        """Extract person name from person.fullName if not provided directly"""
        if v and v != "Unknown Employee":
            return v
        data = info.data if hasattr(info, 'data') else {}
        if 'person' in data and isinstance(data['person'], dict):
            return data['person'].get('fullName', 'Unknown Employee')
        return "Unknown Employee"

    @field_validator('name', mode='before')
    @classmethod
    def extract_company_name(cls, v: Any, info) -> str:
        """Extract company name from company.name if not provided directly"""
        if v and v != "Unknown Company":
            return v
        data = info.data if hasattr(info, 'data') else {}
        if 'company' in data and isinstance(data['company'], dict):
            return data['company'].get('name', 'Unknown Company')
        return "Unknown Company"

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
    enable_historical_comparison: bool = True
    last_updated: datetime = Field(default_factory=datetime.now)

class DataMapping(BaseModel):
    environment: str
    mappings: Dict[str, List[str]] # feature_id -> list of raw field paths
    last_updated: datetime = Field(default_factory=datetime.now)
