"""Artifact Storage authoritative Catalog Table을 추가한다.

Revision ID: 20260809_0016
Revises: 20260808_0015
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0016"
down_revision: str | None = "20260808_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 35개 Table을 변경하지 않고 내부 Catalog Table만 추가한다."""

    op.create_table(
        "artifact_storage_locations",
        sa.Column("storage_location_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("storage_backend", sa.String(), nullable=False),
        sa.Column("storage_domain", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("locator_version", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(storage_backend)) > 0",
            name="ck_artifact_storage_locations_backend_nonempty",
        ),
        sa.CheckConstraint(
            "storage_domain IN ('lm', 'audio', 'vocal', 'music')",
            name="ck_artifact_storage_locations_domain",
        ),
        sa.CheckConstraint(
            "length(storage_key) > 0",
            name="ck_artifact_storage_locations_key_nonempty",
        ),
        sa.CheckConstraint(
            "locator_version >= 1",
            name="ck_artifact_storage_locations_locator_version",
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("storage_location_id"),
        sa.UniqueConstraint(
            "artifact_id",
            name="uq_artifact_storage_locations_artifact",
        ),
        sa.UniqueConstraint(
            "storage_backend",
            "storage_domain",
            "storage_key",
            name="uq_artifact_storage_locations_locator",
        ),
    )


def downgrade() -> None:
    """내부 Catalog Table만 제거하고 기존 35개 Table을 보존한다."""

    op.drop_table("artifact_storage_locations")
