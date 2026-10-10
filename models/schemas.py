from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    VW = "vw"           # Viewer / Worker
    DATA_ENTRY = "data_entry"  # Clinical data entry operator

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.VW

class UserCreate(UserBase):
    password: str

class UserInvite(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.VW
    frontend_url: Optional[str] = None

class UserAcceptInvite(BaseModel):
    token: str
    password: str
    full_name: str

class PasswordResetRequest(BaseModel):
    email: EmailStr
    frontend_url: Optional[str] = None

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    full_name: Optional[str]

class User(UserBase):
    id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True

# Outbreak Detection Schemas

class OutbreakReport(BaseModel):
    location: str
    symptoms: List[str] = Field(default_factory=list)
    cases: int
    date: Optional[str] = None
    classification: str = "Suspected"  # Suspected, Probable, Confirmed
    additional_info: Dict[str, Any] = Field(default_factory=dict)

class ContextData(BaseModel):
    location: str
    security_status: Optional[str] = None
    water_quality: Optional[str] = None
    temperature: Optional[str] = None
    conflict_zone: bool = False
    nearby_facilities: List[str] = Field(default_factory=list)
    recent_news: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)

class ValidationResult(BaseModel):
    valid: bool
    confidence: float
    issues: List[str] = Field(default_factory=list)

class RiskAnalysis(BaseModel):
    risk_level: str  # HIGH, MEDIUM, LOW
    confidence: str
    possible_disease: str
    reason: str

class ConsensusResult(BaseModel):
    final_risk_level: str
    average_confidence: float
    consensus_reached: bool
    agent_opinions: List[RiskAnalysis] = Field(default_factory=list)
    final_reasoning: str

class AlertMessage(BaseModel):
    title: str
    message: str
    recommendations: List[str] = Field(default_factory=list)
    prevention_strategy: Optional[str] = None
    why_urgent: Optional[str] = None

class OutbreakProcessResponse(BaseModel):
    extracted_data: OutbreakReport
    validation: ValidationResult
    risk_analysis: RiskAnalysis
    consensus: Optional[ConsensusResult] = None
    context_research: Optional[ContextData] = None
    alert: AlertMessage
    session_id: str
    metadata: dict = Field(default_factory=dict)
    message: str
    human_validation_required: bool = True
    status: Optional[str] = "pending"
    created_at: Optional[str] = None
    raw_report: Optional[str] = None

class QueryResponse(BaseModel):
    query: str
    response: str
    data_summary: Dict[str, Any] = Field(default_factory=dict)

# Chatbot Schemas
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ChatSession(BaseModel):
    session_id: str
    history: List[ChatMessage] = Field(default_factory=list)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_used: str
    history_count: int


# --- Patient Manual Form Entry ---

class VitalSigns(BaseModel):
    blood_pressure: Optional[str] = None
    pulse: Optional[str] = None
    temperature: Optional[str] = None
    respiratory_rate: Optional[str] = None
    oxygen_saturation: Optional[str] = None
    weight: Optional[str] = None
    height: Optional[str] = None


class PatientRecord(BaseModel):
    # Demographics
    patient_name: str
    sex: Optional[str] = None
    age: Optional[str] = None
    city: Optional[str] = None
    subcity: Optional[str] = None
    woreda: Optional[str] = None
    mrn: Optional[str] = None           # Medical Record Number
    occupation: Optional[str] = None
    date: Optional[str] = None

    # Clinical
    chief_complaint: Optional[str] = None
    history: Optional[str] = None
    physical_exam: Optional[str] = None
    vital_signs: Optional[VitalSigns] = None
    assessment: Optional[str] = None
    past_medical_history: Optional[str] = None
    plan: Optional[str] = None


class PatientRecordResponse(BaseModel):
    id: str
    message: str
    patient_name: str
    mrn: Optional[str] = None
    saved_at: str