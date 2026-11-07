from typing import Any

from pydantic import BaseModel, Field

from app.schemas.fraud import FraudEvent, RiskAssessment
from app.schemas.vision import (
    BoundingBox,
    IdentityMatchResult,
)
from app.vision.liveness import LivenessResult
from app.vision.quality import ImageQualityAssessment


class FramePayload(BaseModel):
    frame_id: str = Field(..., description="Unique frame identifier within batch")
    timestamp_ms: int = Field(..., description="Epoch millisecond timestamp of frame capture")
    image_base64: str = Field(..., description="Base64 encoded JPEG/PNG image data")


class AnalyzeFramesRequest(BaseModel):
    batch_id: str = Field(..., description="Unique batch identifier")
    frames: list[FramePayload] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Batched frames array (strict limit: 1-10 frames per request)",
    )
    client_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Client device and stream telemetry metadata",
    )


class FrameDetectionDetail(BaseModel):
    track_id: int = Field(..., description="Persistent track identifier across frames")
    bbox: BoundingBox = Field(..., description="Bounding box of detected face")
    detection_confidence: float = Field(..., description="Detector confidence score")
    identity_match: IdentityMatchResult | None = Field(
        default=None,
        description="Identity comparison result against candidate reference embedding",
    )
    liveness: LivenessResult | None = Field(
        default=None,
        description="Presentation attack detection / anti-spoofing evaluation result",
    )


class FrameAnalysisResult(BaseModel):
    frame_id: str
    timestamp_ms: int
    faces_detected: int
    quality: ImageQualityAssessment
    liveness: LivenessResult | None = None
    detections: list[FrameDetectionDetail]


class AnalyzeFramesResponse(BaseModel):
    session_id: str
    batch_id: str
    frames_processed: int
    frame_results: list[FrameAnalysisResult]
    confirmed_events: list[FraudEvent]
    current_risk: RiskAssessment
