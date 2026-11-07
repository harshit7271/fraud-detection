from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.frame import AnalyzeFramesResponse


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobEnqueueResponse(BaseModel):
    job_id: str = Field(..., description="Unique asynchronous job identifier")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Job processing status")
    session_id: str = Field(..., description="Target interview session ID")
    frames_count: int = Field(..., description="Number of batched frames queued for CV processing")
    created_at: datetime = Field(..., description="UTC creation timestamp")


class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Unique asynchronous job identifier")
    status: JobStatus = Field(..., description="Current job status")
    session_id: str = Field(..., description="Target interview session ID")
    frames_count: int = Field(..., description="Number of batched frames")
    processing_time_ms: int | None = Field(default=None, description="Total pipeline latency in milliseconds")
    created_at: str | datetime = Field(..., description="Job submission timestamp")
    completed_at: str | datetime | None = Field(default=None, description="Job completion timestamp")
    result: AnalyzeFramesResponse | None = Field(default=None, description="Batch analysis results if completed")
    error_message: str | None = Field(default=None, description="Error message if processing failed")
