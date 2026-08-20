"""Project-level CompositionSnapshot selection을 추가한다.

Revision ID: 20260820_0018
Revises: 20260810_0017
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0018"
down_revision: str | None = "20260810_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 Project와 Snapshot을 변경하지 않고 선택 상태만 추가한다."""

    op.create_index(
        "uq_composition_snapshots_project_identity",
        "composition_snapshots",
        ["project_id", "composition_snapshot_id"],
        unique=True,
    )
    op.create_index(
        "ix_artifacts_version_created",
        "artifacts",
        ["asset_version_id", "created_at", "artifact_id"],
        unique=False,
    )
    op.create_table(
        "project_composition_selections",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("selected_composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["music_projects.project_id"],
            name="fk_project_composition_selections_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "selected_composition_snapshot_id"],
            [
                "composition_snapshots.project_id",
                "composition_snapshots.composition_snapshot_id",
            ],
            name="fk_project_composition_selections_same_project_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint("selected_composition_snapshot_id"),
    )


def downgrade() -> None:
    """선택 상태 Table과 이를 위한 복합 unique Index만 제거한다."""

    op.drop_table("project_composition_selections")
    op.drop_index("ix_artifacts_version_created", table_name="artifacts")
    op.drop_index(
        "uq_composition_snapshots_project_identity",
        table_name="composition_snapshots",
    )
