"""Pipeline orchestration jobs and output files.

Revision ID: 20260729_0004
Revises: 20260729_0003
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("voice_profile_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(100), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("lyrics", sa.Text(), nullable=True),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("pipeline_version", sa.String(50), nullable=False),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column("failed_step", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["voice_profile_id"], ["voice_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_jobs_voice_profile_id", "pipeline_jobs", ["voice_profile_id"]
    )
    op.create_index("ix_pipeline_jobs_status", "pipeline_jobs", ["status"])
    op.create_table(
        "pipeline_files",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["pipeline_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_files_job_id", "pipeline_files", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_files_job_id", table_name="pipeline_files")
    op.drop_table("pipeline_files")
    op.drop_index("ix_pipeline_jobs_status", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_voice_profile_id", table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
