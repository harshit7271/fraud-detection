"""initial enterprise schema

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-11-06 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tenants table
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)

    # 2. Tenant Configs table
    op.create_table(
        "tenant_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("face_match_threshold", sa.Float(), nullable=False, server_default="0.38"),
        sa.Column("face_uncertain_threshold", sa.Float(), nullable=False, server_default="0.25"),
        sa.Column("multiple_faces_debounce_ms", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("face_absence_debounce_ms", sa.Integer(), nullable=False, server_default="3000"),
        sa.Column("event_weights", sa.JSON(), nullable=False),
        sa.Column("risk_bands", sa.JSON(), nullable=False),
        sa.Column("biometric_retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_configs_tenant_id_tenants"), ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_tenant_configs_tenant_id")),
    )

    # 3. Interview Sessions table
    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("interview_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="INITIALIZED"),
        sa.Column("consent_recorded", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_interview_sessions_tenant_id_tenants"), ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_interview_sessions_tenant_id"), "interview_sessions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_interview_sessions_candidate_id"), "interview_sessions", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_interview_sessions_interview_id"), "interview_sessions", ["interview_id"], unique=False)

    # 4. Reference Faces table (Encrypted Biometrics)
    op.create_table(
        "reference_faces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_embedding", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_iv", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=32), nullable=False, server_default="v1-2026"),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("bbox_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name=op.f("fk_reference_faces_session_id_interview_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_reference_faces_tenant_id_tenants"), ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", name=op.f("uq_reference_faces_session_id")),
    )
    op.create_index(op.f("ix_reference_faces_tenant_id"), "reference_faces", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_reference_faces_session_id"), "reference_faces", ["session_id"], unique=True)

    # 5. Fraud Events table
    op.create_table(
        "fraud_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="MEDIUM"),
        sa.Column("evidence_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name=op.f("fk_fraud_events_session_id_interview_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_fraud_events_tenant_id_tenants"), ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_fraud_events_tenant_id"), "fraud_events", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_fraud_events_session_id"), "fraud_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_fraud_events_event_type"), "fraud_events", ["event_type"], unique=False)

    # 6. Fraud Reports table
    op.create_table(
        "fraud_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("fraud_status", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("summary_breakdown", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name=op.f("fk_fraud_reports_session_id_interview_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_fraud_reports_tenant_id_tenants"), ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", name=op.f("uq_fraud_reports_session_id")),
    )
    op.create_index(op.f("ix_fraud_reports_tenant_id"), "fraud_reports", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_fraud_reports_session_id"), "fraud_reports", ["session_id"], unique=True)

    # 7. Processing Jobs table
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("celery_task_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("frames_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], name=op.f("fk_processing_jobs_session_id_interview_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_processing_jobs_tenant_id_tenants"), ondelete="CASCADE"),
        sa.UniqueConstraint("celery_task_id", name=op.f("uq_processing_jobs_celery_task_id")),
    )
    op.create_index(op.f("ix_processing_jobs_tenant_id"), "processing_jobs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_session_id"), "processing_jobs", ["session_id"], unique=False)
    op.create_index(op.f("ix_processing_jobs_celery_task_id"), "processing_jobs", ["celery_task_id"], unique=True)

    # 8. Audit Logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_audit_logs_tenant_id_tenants"), ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_audit_logs_tenant_id"), "audit_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("processing_jobs")
    op.drop_table("fraud_reports")
    op.drop_table("fraud_events")
    op.drop_table("reference_faces")
    op.drop_table("interview_sessions")
    op.drop_table("tenant_configs")
    op.drop_table("tenants")
