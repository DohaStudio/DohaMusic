"""add working preview render manifest

Revision ID: 20260828_0024
Revises: 20260825_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0024"
down_revision: str | Sequence[str] | None = "20260825_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "working_preview_assets",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["music_projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_table(
        "working_preview_renders",
        sa.Column("preview_render_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("rendered_revision", sa.Integer(), nullable=False),
        sa.Column("workspace_job_id", sa.Uuid(), nullable=False),
        sa.Column("preview_asset_id", sa.Uuid(), nullable=False),
        sa.Column("preview_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("payload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rendered_revision >= 0", name="ck_working_preview_non_negative_revision"
        ),
        sa.ForeignKeyConstraint(["preview_asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["preview_asset_version_id"], ["asset_versions.asset_version_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["music_projects.project_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["working_composition_id"],
            ["working_compositions.working_composition_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("preview_render_id"),
        sa.UniqueConstraint("preview_asset_version_id"),
        sa.UniqueConstraint("workspace_job_id", name="uq_working_preview_render_job"),
    )
    op.create_index(
        "ix_working_preview_render_project_id", "working_preview_renders", ["project_id"]
    )
    op.create_index(
        "ix_working_preview_render_working_composition_id",
        "working_preview_renders",
        ["working_composition_id"],
    )
    op.create_index(
        "ix_working_preview_render_preview_asset_id",
        "working_preview_renders",
        ["preview_asset_id"],
    )
    op.create_index(
        "ix_working_preview_render_payload_expires_at",
        "working_preview_renders",
        ["payload_expires_at"],
    )
    op.create_index(
        "ix_working_preview_render_working_revision",
        "working_preview_renders",
        ["working_composition_id", "rendered_revision", "created_at"],
    )
    op.create_table(
        "working_preview_render_tracks",
        sa.Column("preview_render_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("track_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("track_order >= 0", name="ck_working_preview_track_non_negative_order"),
        sa.ForeignKeyConstraint(
            ["preview_render_id"],
            ["working_preview_renders.preview_render_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("preview_render_id", "track_id"),
        sa.UniqueConstraint(
            "preview_render_id", "track_id", name="uq_working_preview_track_identity"
        ),
        sa.UniqueConstraint(
            "preview_render_id", "track_order", name="uq_working_preview_track_order"
        ),
    )
    op.create_table(
        "working_preview_render_clips",
        sa.Column("preview_render_id", sa.Uuid(), nullable=False),
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_order", sa.Integer(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("source_in_us", sa.BigInteger(), nullable=False),
        sa.Column("source_out_us", sa.BigInteger(), nullable=False),
        sa.Column("source_duration_us", sa.BigInteger(), nullable=False),
        sa.Column("timeline_start_us", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "canonical_order >= 0", name="ck_working_preview_clip_non_negative_order"
        ),
        sa.CheckConstraint(
            "source_in_us >= 0", name="ck_working_preview_clip_non_negative_source_in"
        ),
        sa.CheckConstraint(
            "source_duration_us > 0", name="ck_working_preview_clip_positive_duration"
        ),
        sa.CheckConstraint(
            "source_out_us > source_in_us", name="ck_working_preview_clip_non_empty_range"
        ),
        sa.CheckConstraint(
            "source_out_us <= source_duration_us",
            name="ck_working_preview_clip_range_within_source",
        ),
        sa.CheckConstraint(
            "timeline_start_us >= 0", name="ck_working_preview_clip_non_negative_timeline"
        ),
        sa.ForeignKeyConstraint(
            ["preview_render_id", "track_id"],
            [
                "working_preview_render_tracks.preview_render_id",
                "working_preview_render_tracks.track_id",
            ],
            ondelete="RESTRICT",
            name="fk_working_preview_clip_manifest_track",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_version_id"], ["asset_versions.asset_version_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("preview_render_id", "clip_id"),
        sa.UniqueConstraint(
            "preview_render_id", "canonical_order", name="uq_working_preview_clip_order"
        ),
    )
    op.create_index(
        "ix_working_preview_clip_artifact", "working_preview_render_clips", ["source_artifact_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_working_preview_clip_artifact", table_name="working_preview_render_clips")
    op.drop_table("working_preview_render_clips")
    op.drop_table("working_preview_render_tracks")
    op.drop_index(
        "ix_working_preview_render_working_revision", table_name="working_preview_renders"
    )
    op.drop_index(
        "ix_working_preview_render_payload_expires_at", table_name="working_preview_renders"
    )
    op.drop_index(
        "ix_working_preview_render_preview_asset_id", table_name="working_preview_renders"
    )
    op.drop_index(
        "ix_working_preview_render_working_composition_id", table_name="working_preview_renders"
    )
    op.drop_index("ix_working_preview_render_project_id", table_name="working_preview_renders")
    op.drop_table("working_preview_renders")
    op.drop_table("working_preview_assets")
