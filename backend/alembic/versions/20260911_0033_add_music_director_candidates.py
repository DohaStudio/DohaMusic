"""add music director candidate persistence

Revision ID: 20260911_0033
Revises: 20260908_0032
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0033"
down_revision = "20260908_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_director_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("selected_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("applied_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("applied_working_revision", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "composition_snapshot_id"],
            ["composition_snapshots.project_id", "composition_snapshots.composition_snapshot_id"],
            name="fk_music_director_runs_project_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_music_director_runs_project_created",
        "music_director_runs",
        ["project_id", "created_at"],
    )
    op.create_table(
        "music_director_candidates",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("proposal_digest", sa.String(64), nullable=False),
        sa.Column("candidate_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("preview_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0 AND ordinal < 4", name="ck_music_director_candidates_ordinal"
        ),
        sa.CheckConstraint(
            "status IN ('generated', 'rejected', 'applied')",
            name="ck_music_director_candidates_status",
        ),
        sa.CheckConstraint(
            "length(proposal_digest) = 64", name="ck_music_director_candidates_digest"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["music_director_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_asset_version_id"], ["asset_versions.asset_version_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["preview_artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("candidate_id"),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_music_director_candidates_run_ordinal"),
        sa.UniqueConstraint(
            "run_id", "candidate_id", name="uq_music_director_candidates_run_candidate"
        ),
    )
    with op.batch_alter_table("music_director_runs") as batch:
        batch.create_foreign_key(
            "fk_music_director_runs_selected_candidate",
            "music_director_candidates",
            ["run_id", "selected_candidate_id"],
            ["run_id", "candidate_id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_music_director_runs_applied_candidate",
            "music_director_candidates",
            ["run_id", "applied_candidate_id"],
            ["run_id", "candidate_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("music_director_runs") as batch:
        batch.drop_constraint("fk_music_director_runs_applied_candidate", type_="foreignkey")
        batch.drop_constraint("fk_music_director_runs_selected_candidate", type_="foreignkey")
    op.drop_table("music_director_candidates")
    op.drop_index("ix_music_director_runs_project_created", table_name="music_director_runs")
    op.drop_table("music_director_runs")
