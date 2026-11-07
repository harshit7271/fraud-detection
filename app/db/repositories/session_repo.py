import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fraud import FraudEventModel, FraudReportModel
from app.db.models.job import ProcessingJob
from app.db.models.session import InterviewSession, ReferenceFace


class SessionRepository:
    """
    Asynchronous repository for interview sessions, encrypted biometric references,
    fraud events, and proctoring reports with strict tenant isolation queries.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        candidate_id: str,
        interview_id: str,
        consent_recorded: bool,
    ) -> InterviewSession:
        session = InterviewSession(
            id=session_id,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            interview_id=interview_id,
            consent_recorded=consent_recorded,
            status="INITIALIZED",
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def store_reference_face(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        encrypted_embedding: bytes,
        encryption_iv: bytes,
        key_version: str,
        quality_score: float,
        bbox_metadata: dict[str, Any],
    ) -> ReferenceFace:
        ref_face = ReferenceFace(
            session_id=session_id,
            tenant_id=tenant_id,
            encrypted_embedding=encrypted_embedding,
            encryption_iv=encryption_iv,
            key_version=key_version,
            quality_score=quality_score,
            bbox_metadata=bbox_metadata,
        )
        self.db.add(ref_face)
        await self.db.flush()
        return ref_face

    async def get_session(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> InterviewSession | None:
        """Tenant-scoped query preventing cross-tenant data access."""
        query = select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.tenant_id == tenant_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_reference_face(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> ReferenceFace | None:
        query = select(ReferenceFace).where(
            ReferenceFace.session_id == session_id,
            ReferenceFace.tenant_id == tenant_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def record_fraud_event(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        event_type: str,
        timestamp_ms: int,
        duration_ms: int,
        confidence: float,
        severity: str,
        evidence_metadata: dict[str, Any],
    ) -> FraudEventModel:
        event = FraudEventModel(
            session_id=session_id,
            tenant_id=tenant_id,
            event_type=event_type,
            timestamp_ms=timestamp_ms,
            duration_ms=duration_ms,
            confidence=confidence,
            severity=severity,
            evidence_metadata=evidence_metadata,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_fraud_events(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[FraudEventModel]:
        query = (
            select(FraudEventModel)
            .where(
                FraudEventModel.session_id == session_id,
                FraudEventModel.tenant_id == tenant_id,
            )
            .order_by(FraudEventModel.timestamp_ms.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_fraud_report(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        risk_score: float,
        risk_level: str,
        fraud_status: str,
        recommendation: str,
        summary_breakdown: dict[str, Any],
    ) -> FraudReportModel:
        report = FraudReportModel(
            session_id=session_id,
            tenant_id=tenant_id,
            risk_score=risk_score,
            risk_level=risk_level,
            fraud_status=fraud_status,
            recommendation=recommendation,
            summary_breakdown=summary_breakdown,
        )
        self.db.add(report)
        await self.db.flush()
        return report

    async def create_processing_job(
        self,
        job_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        celery_task_id: str,
        frames_count: int,
        status: str = "PENDING",
    ) -> ProcessingJob:
        job = ProcessingJob(
            id=job_id,
            tenant_id=tenant_id,
            session_id=session_id,
            celery_task_id=celery_task_id,
            frames_count=frames_count,
            status=status,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_processing_job(
        self,
        job_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> ProcessingJob | None:
        query = select(ProcessingJob).where(
            ProcessingJob.id == job_id,
            ProcessingJob.tenant_id == tenant_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_processing_job_by_celery_id(
        self,
        celery_task_id: str,
    ) -> ProcessingJob | None:
        query = select(ProcessingJob).where(ProcessingJob.celery_task_id == celery_task_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_processing_job(
        self,
        job_id: uuid.UUID,
        status: str,
        processing_time_ms: int | None = None,
        error_message: str | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> ProcessingJob | None:
        query = select(ProcessingJob).where(ProcessingJob.id == job_id)
        result = await self.db.execute(query)
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if processing_time_ms is not None:
                job.processing_time_ms = processing_time_ms
            if error_message is not None:
                job.error_message = error_message
            if result_payload is not None:
                job.result_payload = result_payload
            await self.db.flush()
        return job
