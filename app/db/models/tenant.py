import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.session import InterviewSession


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    config: Mapped["TenantConfig"] = relationship(
        "TenantConfig",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["InterviewSession"]] = relationship(
        "InterviewSession",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class TenantConfig(Base, TimestampMixin):
    __tablename__ = "tenant_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    face_match_threshold: Mapped[float] = mapped_column(Float, default=0.38, nullable=False)
    face_uncertain_threshold: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    multiple_faces_debounce_ms: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    face_absence_debounce_ms: Mapped[int] = mapped_column(Integer, default=3000, nullable=False)
    event_weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_bands: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    biometric_retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="config")
