from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.fraud import RiskAssessment
from app.schemas.vision import BoundingBox
from app.vision.quality import ImageQualityAssessment


class ReferenceFaceMetadata(BaseModel):
    face_detected: bool = Field(default=True)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: BoundingBox
    quality: ImageQualityAssessment


class SessionRegisterResponse(BaseModel):
    session_id: str = Field(..., description="Unique interview session UUID")
    tenant_id: str = Field(..., description="Tenant identifier")
    candidate_id: str = Field(..., description="Candidate identifier")
    interview_id: str = Field(..., description="Interview identifier")
    status: str = Field(default="INITIALIZED")
    reference_face: ReferenceFaceMetadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionDetailResponse(BaseModel):
    session_id: str
    tenant_id: str
    candidate_id: str
    interview_id: str
    status: str
    consent_recorded: bool
    current_risk: RiskAssessment | None = None
    total_events: int = Field(default=0, description="Total confirmed fraud events")
    created_at: datetime


class FraudReportResponse(BaseModel):
    session_id: str
    tenant_id: str
    candidate_id: str
    interview_id: str
    status: str
    risk_assessment: RiskAssessment
    total_events: int
    confirmed_events: list[dict[str, Any]]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
