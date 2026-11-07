import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FraudEventType(StrEnum):
    MULTIPLE_FACES = "MULTIPLE_FACES"
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    FACE_ABSENT = "FACE_ABSENT"
    LOW_IMAGE_QUALITY = "LOW_IMAGE_QUALITY"
    FACE_OCCLUSION = "FACE_OCCLUSION"
    VIDEO_FEED_INTERRUPTED = "VIDEO_FEED_INTERRUPTED"
    PRESENTATION_ATTACK_SUSPECTED = "PRESENTATION_ATTACK_SUSPECTED"


class FraudSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudStatus(StrEnum):
    CLEARED = "CLEARED"
    SUSPICIOUS = "SUSPICIOUS"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"


class Recommendation(StrEnum):
    NO_ACTION = "NO_ACTION"
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATE = "ESCALATE"


class FraudEvent(BaseModel):
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the fraud event",
    )
    session_id: str = Field(..., description="Interview session ID")
    tenant_id: str = Field(..., description="Tenant ID")
    event_type: FraudEventType = Field(..., description="Type of detected event")
    timestamp_ms: int = Field(..., description="Epoch millisecond timestamp of event")
    duration_ms: int = Field(default=0, description="Duration anomaly persisted in ms")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    severity: FraudSeverity = Field(default=FraudSeverity.MEDIUM)
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class RiskAssessment(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Normalized risk score (0-100)")
    risk_level: RiskLevel = Field(..., description="Categorical risk band")
    fraud_status: FraudStatus = Field(..., description="Overall session fraud evaluation")
    recommendation: Recommendation = Field(..., description="Actionable recommendation")
    total_events: int = Field(default=0)
    event_breakdown: dict[str, int] = Field(default_factory=dict)
    scoring_explanation: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
