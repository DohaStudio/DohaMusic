"""Stem separation jobs and output files.

Revision ID: 20260729_0002
Revises: 20260729_0001
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stem_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["generated_files.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stem_jobs_source_file_id", "stem_jobs", ["source_file_id"])
    op.create_index("ix_stem_jobs_status", "stem_jobs", ["status"])
    op.create_table(
        "stem_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["stem_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stem_files_job_id", "stem_files", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_stem_files_job_id", table_name="stem_files")
    op.drop_table("stem_files")
    op.drop_index("ix_stem_jobs_status", table_name="stem_jobs")
    op.drop_index("ix_stem_jobs_source_file_id", table_name="stem_jobs")
    op.drop_table("stem_jobs")
