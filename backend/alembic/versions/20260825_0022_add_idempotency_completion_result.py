"""Add revision-safe idempotency completion results.

Revision ID: 20260825_0022
Revises: 20260824_0021
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0022"
down_revision: str | None = "20260824_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep legacy rows valid while adding a versioned completion result."""

    op.add_column(
        "idempotency_records",
        sa.Column(
            "completed_revision",
            sa.BigInteger(),
            sa.CheckConstraint(
                "completed_revision IS NULL OR completed_revision >= 0",
                name="ck_idempotency_records_non_negative_completed_revision",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "idempotency_records",
        sa.Column("result_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "idempotency_records",
        sa.Column(
            "result_version",
            sa.Integer(),
            sa.CheckConstraint(
                "result_version IS NULL OR result_version > 0",
                name="ck_idempotency_records_positive_result_version",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "idempotency_records",
        sa.Column("result_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Retain legacy replay fields and remove only the new result columns."""

    op.drop_column("idempotency_records", "result_payload")
    op.drop_column("idempotency_records", "result_version")
    op.drop_column("idempotency_records", "result_type")
    op.drop_column("idempotency_records", "completed_revision")
