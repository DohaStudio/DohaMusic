"""Durable PayloadLocator persistence foundation을 추가한다.

Revision ID: 20260825_0023
Revises: 20260825_0022
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0023"
down_revision: str | None = "20260825_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 row를 바꾸지 않고 locator table과 scope FK 기반을 추가한다."""

    op.create_index(
        "uq_provider_job_bindings_workspace_identity",
        "provider_job_bindings",
        ["workspace_job_id", "provider_job_binding_id"],
        unique=True,
    )
    op.create_table(
        "payload_locators",
        sa.Column("payload_locator_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_job_id", sa.Uuid(), nullable=False),
        sa.Column("provider_job_binding_id", sa.Uuid(), nullable=False),
        sa.Column("payload_ordinal", sa.Integer(), nullable=False),
        sa.Column("provider_artifact_id", sa.String(200), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("artifact_kind", sa.String(32), nullable=False),
        sa.Column("expected_checksum_algorithm", sa.String(16), nullable=False),
        sa.Column("expected_payload_checksum", sa.String(64), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expected_media_type", sa.String(128), nullable=False),
        sa.Column("source_available_until", sa.DateTime(timezone=True)),
        sa.Column("locator_expires_at", sa.DateTime(timezone=True)),
        sa.Column("staging_status", sa.String(32), nullable=False),
        sa.Column("staging_backend", sa.String(32)),
        sa.Column("staging_key", sa.String(512)),
        sa.Column("actual_checksum_algorithm", sa.String(16)),
        sa.Column("actual_payload_checksum", sa.String(64)),
        sa.Column("actual_size_bytes", sa.BigInteger()),
        sa.Column("actual_media_type", sa.String(128)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("ingested_artifact_id", sa.Uuid()),
        sa.Column("ingested_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(32)),
        sa.Column("cleanup_requested_at", sa.DateTime(timezone=True)),
        sa.Column("cleanup_completed_at", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "payload_ordinal >= 0", name="ck_payload_locators_ordinal_nonnegative"
        ),
        sa.CheckConstraint(
            "expected_checksum_algorithm = 'sha256' "
            "AND length(expected_payload_checksum) = 64 "
            "AND expected_size_bytes > 0",
            name="ck_payload_locators_expected_integrity",
        ),
        sa.CheckConstraint(
            "lifecycle_revision >= 0",
            name="ck_payload_locators_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="ck_payload_locators_revocation_pair",
        ),
        sa.CheckConstraint(
            "(staging_status = 'source_bound' AND staging_backend IS NULL "
            "AND staging_key IS NULL AND actual_checksum_algorithm IS NULL "
            "AND actual_payload_checksum IS NULL AND actual_size_bytes IS NULL "
            "AND actual_media_type IS NULL AND verified_at IS NULL "
            "AND ingested_artifact_id IS NULL AND ingested_at IS NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'verified_staged' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ingested_artifact_id IS NULL AND ingested_at IS NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'ingested' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'cleanup_pending' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ((ingested_artifact_id IS NULL AND ingested_at IS NULL) OR "
            "(ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL)) "
            "AND cleanup_requested_at IS NOT NULL "
            "AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'cleaned' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ((ingested_artifact_id IS NULL AND ingested_at IS NULL) OR "
            "(ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL)) "
            "AND cleanup_requested_at IS NOT NULL "
            "AND cleanup_completed_at IS NOT NULL)",
            name="ck_payload_locators_lifecycle_facts",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_job_id"],
            ["jobs.job_id"],
            name="fk_payload_locators_workspace_job_id_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_job_id", "provider_job_binding_id"],
            [
                "provider_job_bindings.workspace_job_id",
                "provider_job_bindings.provider_job_binding_id",
            ],
            name="fk_payload_locators_binding_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingested_artifact_id"],
            ["artifacts.artifact_id"],
            name="fk_payload_locators_ingested_artifact_id_artifacts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("payload_locator_id", name="pk_payload_locators"),
        sa.UniqueConstraint(
            "provider_job_binding_id",
            "payload_ordinal",
            name="uq_payload_locators_binding_ordinal",
        ),
        sa.UniqueConstraint(
            "provider_job_binding_id",
            "provider_artifact_id",
            "role",
            "source_id",
            name="uq_payload_locators_source_identity",
        ),
    )
    op.create_index(
        "ix_payload_locators_binding_history",
        "payload_locators",
        ["provider_job_binding_id", "payload_ordinal", "created_at"],
    )
    op.create_index(
        "ix_payload_locators_cleanup_scan",
        "payload_locators",
        ["staging_status", "cleanup_requested_at"],
    )
    op.create_index(
        "ix_payload_locators_source_expiry",
        "payload_locators",
        ["source_available_until"],
    )
    op.create_index(
        "ix_payload_locators_policy_expiry",
        "payload_locators",
        ["locator_expires_at"],
    )
    op.create_index(
        "ix_payload_locators_ingested_artifact",
        "payload_locators",
        ["ingested_artifact_id"],
    )


def downgrade() -> None:
    """PayloadLocator 전용 table/index와 binding scope index만 제거한다."""

    op.drop_index(
        "ix_payload_locators_ingested_artifact", table_name="payload_locators"
    )
    op.drop_index("ix_payload_locators_policy_expiry", table_name="payload_locators")
    op.drop_index("ix_payload_locators_source_expiry", table_name="payload_locators")
    op.drop_index("ix_payload_locators_cleanup_scan", table_name="payload_locators")
    op.drop_index("ix_payload_locators_binding_history", table_name="payload_locators")
    op.drop_table("payload_locators")
    op.drop_index(
        "uq_provider_job_bindings_workspace_identity",
        table_name="provider_job_bindings",
    )
