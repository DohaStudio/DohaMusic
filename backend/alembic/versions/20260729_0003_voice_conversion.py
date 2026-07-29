"""Voice conversion jobs and output files.

Revision ID: 20260729_0003
Revises: 20260729_0002
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_conversion_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_file_id", sa.String(36), nullable=False),
        sa.Column("voice_profile_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model_name", sa.String(150), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_file_id"], ["stem_files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["voice_profile_id"], ["voice_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_conversion_jobs_source_file_id", "voice_conversion_jobs", ["source_file_id"])
    op.create_index("ix_voice_conversion_jobs_voice_profile_id", "voice_conversion_jobs", ["voice_profile_id"])
    op.create_index("ix_voice_conversion_jobs_status", "voice_conversion_jobs", ["status"])
    op.create_table(
        "voice_conversion_files",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["voice_conversion_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_conversion_files_job_id", "voice_conversion_files", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_voice_conversion_files_job_id", table_name="voice_conversion_files")
    op.drop_table("voice_conversion_files")
    op.drop_index("ix_voice_conversion_jobs_status", table_name="voice_conversion_jobs")
    op.drop_index("ix_voice_conversion_jobs_voice_profile_id", table_name="voice_conversion_jobs")
    op.drop_index("ix_voice_conversion_jobs_source_file_id", table_name="voice_conversion_jobs")
    op.drop_table("voice_conversion_jobs")
