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

class Activity(BaseModel):
    id: str
    name: str
    role_required: str = "worker" # Fallback if host API doesn't provide it
    environment: str = "" # Injected by router
    
    # Additional fields from real API
    project: Optional[Any] = None
    code: Optional[str] = None
    note: Optional[str] = None
    typeActivity: Optional[str] = None
    dtEnd: Optional[str] = None
    type: Optional[str] = None
    productivityType: Optional[str] = None
    operations: Optional[List[Any]] = None

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)

class Employment(BaseModel):
    id: str
    name: str = "Unknown Employee"
    role: str = "worker" # Fallback if host API doesn't provide it
    environment: str = "" # Injected by router
    preferences: Optional[List[float]] = Field(default_factory=list)
    
    # Additional fields from real API
    company: Optional[Dict[str, Any]] = None
    person: Optional[Dict[str, Any]] = None
    dtHired: Optional[str] = None
    dtDismissed: Optional[str] = None
    badge: Optional[Dict[str, Any]] = None

    @field_validator('id', mode='before')
    @classmethod
    def transform_id(cls, v: Any) -> str:
        return str(v)
    
    @field_validator('name', mode='before')
    @classmethod
    def extract_name(cls, v: Any, info) -> str:
        """Extract name from person.fullName if not provided directly"""
        if v and v != "Unknown Employee":
            return v
        # Try to get from person.fullName
        data = info.data if hasattr(info, 'data') else {}
        if 'person' in data and isinstance(data['person'], dict):
            return data['person'].get('fullName', 'Unknown Employee')
        return "Unknown Employee"

class AgentRequest(BaseModel):
    environment: str
    timestamp: int
    payload: dict # Flexible payload depending on action
