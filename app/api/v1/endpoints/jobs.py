import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.redis import RedisService, get_redis_service
from app.middleware.auth import TenantContext, get_current_tenant
from app.schemas.job import JobStatusResponse

router = APIRouter(prefix="/fraud/jobs", tags=["Background Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Asynchronous Job Status",
)
async def get_job_status(
    job_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    redis_service: Annotated[RedisService, Depends(get_redis_service)],
) -> JobStatusResponse:
    """
    Retrieves the status, latency, and analysis results of an asynchronous frame processing job.
    Uses Redis cache for instant sub-millisecond retrieval, falling back to PostgreSQL.
    """
    # 1. Check Redis cache
    cached = await redis_service.get_job_status(job_id)
    if cached is not None:
        return JobStatusResponse(**cached)

    # 2. Check PostgreSQL database
    try:
        from app.db.repositories.session_repo import SessionRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            repo = SessionRepository(db)
            job = await repo.get_processing_job(
                job_id=uuid.UUID(job_id),
                tenant_id=uuid.UUID(tenant.tenant_id),
            )
            if job is not None:
                return JobStatusResponse(
                    job_id=str(job.id),
                    status=job.status,  # type: ignore[arg-type]
                    session_id=str(job.session_id),
                    frames_count=job.frames_count,
                    processing_time_ms=job.processing_time_ms,
                    created_at=job.created_at.isoformat(),
                    completed_at=job.updated_at.isoformat() if job.status in ("COMPLETED", "FAILED") else None,
                    result=job.result_payload,  # type: ignore[arg-type]
                    error_message=job.error_message,
                )
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job {job_id} not found",
    )
