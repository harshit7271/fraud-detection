from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Overall service status")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the check",
    )


class ReadinessResponse(BaseModel):
    status: str = Field(default="ready", description="Service readiness status")
    models_loaded: bool = Field(..., description="Whether CV model weights exist on disk")
    yunet_available: bool = Field(..., description="YuNet model presence")
    sface_available: bool = Field(..., description="SFace model presence")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the check",
    )
