import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.redis import RedisService, get_redis_service
from app.middleware.auth import (
    TenantContext,
    get_current_tenant,
    verify_tenant_boundary,
)
from app.schemas.frame import AnalyzeFramesRequest, AnalyzeFramesResponse
from app.schemas.job import JobEnqueueResponse, JobStatus
from app.services.analysis_service import AnalysisService, get_analysis_service
from app.workers.tasks import process_frame_batch_task

router = APIRouter(prefix="/fraud/sessions", tags=["Frame Analysis"])


@router.post(
    "/{session_id}/analyze",
    response_model=AnalyzeFramesResponse | JobEnqueueResponse,
    summary="Analyze Interview Video Frames",
)
def analyze_frames(
    session_id: str,
    payload: AnalyzeFramesRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    redis_service: Annotated[RedisService, Depends(get_redis_service)],
    response: Response,
    async_mode: bool = Query(
        default=False,
        description="When true, offloads frame processing to Celery background workers and returns HTTP 202 with job_id.",
    ),
) -> AnalyzeFramesResponse | JobEnqueueResponse:
    """
    Analyzes a batch of candidate webcam frames against the registered reference embedding.
    Supports both synchronous processing (real-time low-latency mode) and asynchronous
    Celery background worker processing (high-throughput batch proctoring mode).
    """
    if "tenant_id" in payload.client_metadata:
        verify_tenant_boundary(str(payload.client_metadata["tenant_id"]), tenant)

    if async_mode:
        # 1. Validate session existence and tenant ownership
        service.session_service.get_session(session_id, tenant.tenant_id)

        job_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)

        # 2. Record initial PENDING state in cache
        import asyncio

        initial_state = {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "session_id": session_id,
            "frames_count": len(payload.frames),
            "processing_time_ms": None,
            "created_at": created_at.isoformat(),
            "completed_at": None,
            "result": None,
            "error_message": None,
        }
        try:
            asyncio.run(redis_service.set_job_status(job_id, initial_state))
        except Exception:
            pass

        # 3. Dispatch to Celery background worker queue
        process_frame_batch_task.apply_async(
            args=[session_id, tenant.tenant_id, payload.model_dump(mode="json"), job_id],
            task_id=job_id,
        )

        response.status_code = status.HTTP_202_ACCEPTED
        return JobEnqueueResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            session_id=session_id,
            frames_count=len(payload.frames),
            created_at=created_at,
        )

    # Synchronous processing mode
    response.status_code = status.HTTP_200_OK
    return service.analyze_batch(
        session_id=session_id,
        tenant_id=tenant.tenant_id,
        request=payload,
    )
