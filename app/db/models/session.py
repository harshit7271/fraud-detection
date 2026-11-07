import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.fraud import FraudEventModel, FraudReportModel
    from app.db.models.tenant import Tenant


class InterviewSession(Base, TimestampMixin):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    candidate_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    interview_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="INITIALIZED", nullable=False)
    consent_recorded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="sessions")
    reference_face: Mapped["ReferenceFace"] = relationship(
        "ReferenceFace",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    fraud_events: Mapped[list["FraudEventModel"]] = relationship(
        "FraudEventModel",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    fraud_report: Mapped["FraudReportModel | None"] = relationship(
        "FraudReportModel",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ReferenceFace(Base, TimestampMixin):
    __tablename__ = "reference_faces"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Encrypted Biometric Representation at Rest (AES-256-GCM)
    encrypted_embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[str] = mapped_column(String(32), default="v1-2026", nullable=False)

    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    session: Mapped["InterviewSession"] = relationship("InterviewSession", back_populates="reference_face")
