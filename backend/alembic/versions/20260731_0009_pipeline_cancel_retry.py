"""Pipeline cooperative cancellation and retry relationship.

Revision ID: 20260731_0009
Revises: 20260731_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0009"
down_revision: str | None = "20260731_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_jobs") as batch:
        batch.add_column(
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("retry_of_job_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("input_snapshot", sa.JSON(), nullable=True))
        batch.create_index("ix_pipeline_jobs_retry_of_job_id", ["retry_of_job_id"])
        batch.create_foreign_key(
            "fk_pipeline_jobs_retry_of_job_id_pipeline_jobs",
            "pipeline_jobs",
            ["retry_of_job_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text("UPDATE pipeline_jobs SET input_snapshot = '{}' WHERE input_snapshot IS NULL")
    )


def downgrade() -> None:
    with op.batch_alter_table("pipeline_jobs") as batch:
        batch.drop_constraint("fk_pipeline_jobs_retry_of_job_id_pipeline_jobs", type_="foreignkey")
        batch.drop_index("ix_pipeline_jobs_retry_of_job_id")
        batch.drop_column("input_snapshot")
        batch.drop_column("retry_of_job_id")
        batch.drop_column("cancelled_at")
        batch.drop_column("cancel_requested_at")
