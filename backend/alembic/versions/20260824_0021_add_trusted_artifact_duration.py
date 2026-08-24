"""Artifact에 trusted integer-microsecond duration metadata를 추가한다.

Revision ID: 20260824_0021
Revises: 20260824_0020
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0021"
down_revision: str | None = "20260824_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 row와 payload를 읽거나 backfill하지 않고 nullable metadata를 추가한다."""

    op.add_column(
        "artifacts",
        sa.Column(
            "duration_us",
            sa.BigInteger(),
            sa.CheckConstraint(
                "duration_us IS NULL OR duration_us > 0",
                name="ck_artifacts_positive_duration_us",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Artifact row와 payload는 보존하고 trusted duration column만 제거한다."""

    op.drop_column("artifacts", "duration_us")
