import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Task

from app.core.redis import get_redis_service
from app.db.session import async_session_factory
from app.schemas.frame import AnalyzeFramesRequest
from app.schemas.job import JobStatus
from app.services.analysis_service import AnalysisService
from app.workers.celery_app import (
    celery_app,
    get_worker_detector,
    get_worker_quality_assessor,
    get_worker_recognizer,
)

logger = logging.getLogger("app.workers.tasks")


async def _update_job_in_db_and_cache(
    job_id: str,
    status: str,
    frames_count: int,
    session_id: str,
    created_at: str,
    processing_time_ms: int | None = None,
    error_message: str | None = None,
    result_payload: dict[str, Any] | None = None,
) -> None:
    """Updates job status in both Redis cache and PostgreSQL processing_jobs table."""
    completed_at = datetime.now(UTC).isoformat() if status in (JobStatus.COMPLETED, JobStatus.FAILED) else None

    # 1. Update Redis Cache (for fast sub-millisecond polling)
    redis_service = get_redis_service()
    cache_payload: dict[str, Any] = {
        "job_id": job_id,
        "status": status,
        "session_id": session_id,
        "frames_count": frames_count,
        "processing_time_ms": processing_time_ms,
        "created_at": created_at,
        "completed_at": completed_at,
        "result": result_payload,
        "error_message": error_message,
    }
    await redis_service.set_job_status(job_id, cache_payload)

    # 2. Update PostgreSQL processing_jobs row (durable audit record)
    try:
        from app.db.repositories.session_repo import SessionRepository

        async with async_session_factory() as db:
            repo = SessionRepository(db)
            await repo.update_processing_job(
                job_id=uuid.UUID(job_id),
                status=status,
                processing_time_ms=processing_time_ms,
                error_message=error_message,
                result_payload=result_payload,
            )
            await db.commit()
    except Exception as e:
        # Non-fatal if DB is offline or in memory-only test mode
        logger.debug(f"DB update skipped for job {job_id}: {e}")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name="fraud.process_frame_batch",
)
def process_frame_batch_task(
    self: Task,
    session_id: str,
    tenant_id: str,
    request_dict: dict[str, Any],
    job_id: str,
) -> dict[str, Any]:
    """
    Celery background task: Analyzes a batch of candidate webcam frames asynchronously.
    Uses pre-warmed worker CV models, tracks processing latency, and records status in
    both Redis and PostgreSQL.
    """
    start_time = time.time()
    frames = request_dict.get("frames", [])
    frames_count = len(frames)
    created_at = request_dict.get("created_at") or datetime.now(UTC).isoformat()

    logger.info(f"Worker starting job {job_id} for session {session_id} ({frames_count} frames)")

    # Mark as PROCESSING
    try:
        asyncio.run(
            _update_job_in_db_and_cache(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                frames_count=frames_count,
                session_id=session_id,
                created_at=created_at,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to record PROCESSING status for job {job_id}: {e}")

    try:
        # Reconstruct Pydantic request
        parsed_request = AnalyzeFramesRequest.model_validate(request_dict)

        # Inject worker CV singletons
        detector = get_worker_detector()
        recognizer = get_worker_recognizer()
        quality_assessor = get_worker_quality_assessor()

        service = AnalysisService(
            detector=detector,
            recognizer=recognizer,
            quality_assessor=quality_assessor,
        )

        # Execute CV batch pipeline
        analysis_result = service.analyze_batch(
            session_id=session_id,
            tenant_id=tenant_id,
            request=parsed_request,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)
        result_dict = analysis_result.model_dump(mode="json")

        # Update to COMPLETED
        asyncio.run(
            _update_job_in_db_and_cache(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                frames_count=frames_count,
                session_id=session_id,
                created_at=created_at,
                processing_time_ms=processing_time_ms,
                result_payload=result_dict,
            )
        )

        logger.info(f"Worker completed job {job_id} in {processing_time_ms}ms")
        return result_dict

    except Exception as exc:
        processing_time_ms = int((time.time() - start_time) * 1000)
        err_msg = str(exc)
        logger.error(f"Error processing job {job_id}: {err_msg}", exc_info=True)

        is_final_attempt = self.request.retries >= self.max_retries
        final_status = JobStatus.FAILED if is_final_attempt else JobStatus.PROCESSING

        asyncio.run(
            _update_job_in_db_and_cache(
                job_id=job_id,
                status=final_status,
                frames_count=frames_count,
                session_id=session_id,
                created_at=created_at,
                processing_time_ms=processing_time_ms,
                error_message=err_msg,
            )
        )

        # Retry with exponential backoff if retries remaining
        if not is_final_attempt:
            raise self.retry(exc=exc, countdown=5 * (2**self.request.retries)) from exc
        raise exc
