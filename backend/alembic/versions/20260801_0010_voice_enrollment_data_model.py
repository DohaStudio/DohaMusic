"""Guided Voice Enrollment persistence model and legacy profile backfill.

Revision ID: 20260801_0010
Revises: 20260731_0009
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0010"
down_revision: str | None = "20260731_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SAMPLE_NAMESPACE = uuid.UUID("809243d3-2520-43a6-b8d6-482698b222a6")


def _legacy_sample_id(profile_id: str) -> str:
    return str(uuid.uuid5(LEGACY_SAMPLE_NAMESPACE, profile_id))


def upgrade() -> None:
    op.create_table(
        "voice_enrollments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        sa.Column("profile_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("consent_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_policy_version", sa.String(length=50), nullable=True),
        sa.Column("consent_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voice_profile_id", sa.String(length=36), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column(
            "cleanup_status",
            sa.String(length=32),
            nullable=False,
            server_default="NOT_REQUESTED",
        ),
        sa.Column("cleanup_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["voice_profile_id"],
            ["voice_profiles.id"],
            name="fk_voice_enrollments_voice_profile_id_voice_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("voice_profile_id", name="uq_voice_enrollments_voice_profile_id"),
    )
    op.create_index(
        "ix_voice_enrollments_status_expires_at",
        "voice_enrollments",
        ["status", "expires_at"],
    )
    op.create_index("ix_voice_enrollments_cleanup_status", "voice_enrollments", ["cleanup_status"])

    op.create_table(
        "voice_samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("enrollment_id", sa.String(length=36), nullable=True),
        sa.Column("voice_profile_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("prompt_id", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UPLOADED"),
        sa.Column("original_content_type", sa.String(length=100), nullable=True),
        sa.Column("original_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("original_storage_path", sa.String(length=500), nullable=True),
        sa.Column("normalized_content_type", sa.String(length=100), nullable=True),
        sa.Column("normalized_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("normalized_storage_path", sa.String(length=500), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("bit_depth", sa.Integer(), nullable=True),
        sa.Column("quality_status", sa.String(length=20), nullable=True),
        sa.Column("quality_warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "enrollment_id IS NOT NULL OR voice_profile_id IS NOT NULL",
            name="ck_voice_samples_has_owner",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["voice_enrollments.id"],
            name="fk_voice_samples_enrollment_id_voice_enrollments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voice_profile_id"],
            ["voice_profiles.id"],
            name="fk_voice_samples_voice_profile_id_voice_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_samples_enrollment_id_status",
        "voice_samples",
        ["enrollment_id", "status"],
    )
    op.create_index(
        "ix_voice_samples_voice_profile_id_status",
        "voice_samples",
        ["voice_profile_id", "status"],
    )
    op.create_index(
        "ix_voice_samples_status_expires_at",
        "voice_samples",
        ["status", "expires_at"],
    )

    bind = op.get_bind()
    profiles = (
        bind.execute(
            sa.text(
                "SELECT id, reference_file_path, mime_type, size_bytes, duration_seconds, "
                "sample_rate, channels, status, quality_warnings, created_at, updated_at "
                "FROM voice_profiles"
            )
        )
        .mappings()
        .all()
    )
    active_references: list[tuple[str, str]] = []
    for profile in profiles:
        sample_id = _legacy_sample_id(profile["id"])
        promoted = profile["status"] == "READY"
        bind.execute(
            sa.text(
                "INSERT INTO voice_samples ("
                "id, enrollment_id, voice_profile_id, source_type, category, status, "
                "normalized_content_type, normalized_size_bytes, normalized_storage_path, "
                "duration_seconds, sample_rate, channels, quality_warnings, created_at, updated_at"
                ") VALUES ("
                ":id, NULL, :profile_id, 'LEGACY_REFERENCE', 'legacy', :status, "
                ":mime_type, :size_bytes, :path, :duration_seconds, :sample_rate, :channels, "
                ":quality_warnings, :created_at, :updated_at)"
            ),
            {
                "id": sample_id,
                "profile_id": profile["id"],
                "status": "PROMOTED" if promoted else "FAILED",
                "mime_type": profile["mime_type"],
                "size_bytes": profile["size_bytes"],
                "path": profile["reference_file_path"],
                "duration_seconds": profile["duration_seconds"],
                "sample_rate": profile["sample_rate"],
                "channels": profile["channels"],
                "quality_warnings": profile["quality_warnings"] or "[]",
                "created_at": profile["created_at"] or datetime.now(UTC),
                "updated_at": profile["updated_at"] or datetime.now(UTC),
            },
        )
        if promoted:
            active_references.append((profile["id"], sample_id))

    with op.batch_alter_table("voice_profiles") as batch:
        batch.add_column(
            sa.Column("active_reference_sample_id", sa.String(length=36), nullable=True)
        )
        batch.create_unique_constraint(
            "uq_voice_profiles_active_reference_sample_id",
            ["active_reference_sample_id"],
        )
        batch.create_foreign_key(
            "fk_voice_profiles_active_reference_sample_id_voice_samples",
            "voice_samples",
            ["active_reference_sample_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    for profile_id, sample_id in active_references:
        bind.execute(
            sa.text(
                "UPDATE voice_profiles SET active_reference_sample_id = :sample_id "
                "WHERE id = :profile_id"
            ),
            {"profile_id": profile_id, "sample_id": sample_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    enrollment_count = bind.scalar(sa.text("SELECT COUNT(*) FROM voice_enrollments"))
    nonlegacy_count = bind.scalar(
        sa.text("SELECT COUNT(*) FROM voice_samples WHERE source_type <> 'LEGACY_REFERENCE'")
    )
    if enrollment_count or nonlegacy_count:
        raise RuntimeError("Cannot downgrade voice enrollment schema while enrollment data exists")

    with op.batch_alter_table("voice_profiles") as batch:
        batch.drop_constraint(
            "fk_voice_profiles_active_reference_sample_id_voice_samples",
            type_="foreignkey",
        )
        batch.drop_constraint("uq_voice_profiles_active_reference_sample_id", type_="unique")
        batch.drop_column("active_reference_sample_id")
    op.drop_index("ix_voice_samples_status_expires_at", table_name="voice_samples")
    op.drop_index("ix_voice_samples_voice_profile_id_status", table_name="voice_samples")
    op.drop_index("ix_voice_samples_enrollment_id_status", table_name="voice_samples")
    op.drop_table("voice_samples")
    op.drop_index("ix_voice_enrollments_cleanup_status", table_name="voice_enrollments")
    op.drop_index("ix_voice_enrollments_status_expires_at", table_name="voice_enrollments")
    op.drop_table("voice_enrollments")
