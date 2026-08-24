"""Clip domain mutable draft와 immutable arrangement table을 추가한다.

Revision ID: 20260824_0020
Revises: 20260821_0019
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0020"
down_revision: str | None = "20260821_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 Snapshot row를 바꾸지 않고 5개 additive table을 만든다."""

    op.create_table(
        "working_compositions",
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("base_composition_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("mix_settings", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_working_compositions_non_negative_revision"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["music_projects.project_id"],
            name="fk_working_compositions_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "base_composition_snapshot_id"],
            [
                "composition_snapshots.project_id",
                "composition_snapshots.composition_snapshot_id",
            ],
            name="fk_working_compositions_same_project_base_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("working_composition_id", name="pk_working_compositions"),
        sa.UniqueConstraint("project_id", name="uq_working_compositions_project"),
    )
    op.create_index(
        "ix_working_compositions_base_snapshot",
        "working_compositions",
        ["base_composition_snapshot_id"],
        unique=False,
    )

    op.create_table(
        "composition_tracks",
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("track_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("track_order", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("track_type = 'audio'", name="ck_composition_tracks_audio_type"),
        sa.CheckConstraint("track_order >= 0", name="ck_composition_tracks_non_negative_order"),
        sa.ForeignKeyConstraint(
            ["working_composition_id"],
            ["working_compositions.working_composition_id"],
            name="fk_composition_tracks_working_composition",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("track_id", name="pk_composition_tracks"),
        sa.UniqueConstraint(
            "working_composition_id",
            "track_id",
            name="uq_composition_tracks_working_identity",
        ),
    )
    op.create_index(
        "uq_composition_tracks_active_order",
        "composition_tracks",
        ["working_composition_id", "track_order"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_composition_tracks_active_order",
        "composition_tracks",
        ["working_composition_id", "deleted_at", "track_order", "track_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_tracks_deleted_at",
        "composition_tracks",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "composition_clips",
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("timeline_start", sa.BigInteger(), nullable=False),
        sa.Column("source_in", sa.BigInteger(), nullable=False),
        sa.Column("source_out", sa.BigInteger(), nullable=False),
        sa.Column("source_duration", sa.BigInteger(), nullable=False),
        sa.Column("split_from_clip_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("timeline_start >= 0", name="ck_composition_clips_non_negative_start"),
        sa.CheckConstraint("source_in >= 0", name="ck_composition_clips_non_negative_source_in"),
        sa.CheckConstraint("source_duration > 0", name="ck_composition_clips_positive_duration"),
        sa.CheckConstraint("source_out > source_in", name="ck_composition_clips_non_empty_range"),
        sa.CheckConstraint(
            "source_out <= source_duration",
            name="ck_composition_clips_range_within_source",
        ),
        sa.ForeignKeyConstraint(
            ["working_composition_id"],
            ["working_compositions.working_composition_id"],
            name="fk_composition_clips_working_composition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["working_composition_id", "track_id"],
            [
                "composition_tracks.working_composition_id",
                "composition_tracks.track_id",
            ],
            name="fk_composition_clips_same_working_track",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["working_composition_id", "split_from_clip_id"],
            ["composition_clips.working_composition_id", "composition_clips.clip_id"],
            name="fk_composition_clips_same_working_split_parent",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_version_id"],
            ["asset_versions.asset_version_id"],
            name="fk_composition_clips_source_asset_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("clip_id", name="pk_composition_clips"),
        sa.UniqueConstraint(
            "working_composition_id",
            "clip_id",
            name="uq_composition_clips_working_identity",
        ),
    )
    op.create_index(
        "ix_composition_clips_active_timeline",
        "composition_clips",
        ["track_id", "deleted_at", "timeline_start", "clip_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_clips_source_asset_version",
        "composition_clips",
        ["source_asset_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_clips_split_parent",
        "composition_clips",
        ["split_from_clip_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_clips_deleted_at",
        "composition_clips",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "composition_snapshot_tracks",
        sa.Column("snapshot_track_id", sa.Uuid(), nullable=False),
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_track_id", sa.Uuid(), nullable=False),
        sa.Column("track_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("track_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "track_type = 'audio'", name="ck_composition_snapshot_tracks_audio_type"
        ),
        sa.CheckConstraint(
            "track_order >= 0",
            name="ck_composition_snapshot_tracks_non_negative_order",
        ),
        sa.ForeignKeyConstraint(
            ["composition_snapshot_id"],
            ["composition_snapshots.composition_snapshot_id"],
            name="fk_composition_snapshot_tracks_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_track_id", name="pk_composition_snapshot_tracks"),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "snapshot_track_id",
            name="uq_composition_snapshot_tracks_snapshot_identity",
        ),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "canonical_track_id",
            name="uq_composition_snapshot_tracks_canonical_identity",
        ),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "track_order",
            name="uq_composition_snapshot_tracks_order",
        ),
    )
    op.create_index(
        "ix_composition_snapshot_tracks_order",
        "composition_snapshot_tracks",
        ["composition_snapshot_id", "track_order", "snapshot_track_id"],
        unique=False,
    )

    op.create_table(
        "composition_snapshot_clips",
        sa.Column("snapshot_clip_id", sa.Uuid(), nullable=False),
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_track_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_clip_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("timeline_start", sa.BigInteger(), nullable=False),
        sa.Column("source_in", sa.BigInteger(), nullable=False),
        sa.Column("source_out", sa.BigInteger(), nullable=False),
        sa.Column("source_duration", sa.BigInteger(), nullable=False),
        sa.Column("split_from_clip_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "timeline_start >= 0",
            name="ck_composition_snapshot_clips_non_negative_start",
        ),
        sa.CheckConstraint(
            "source_in >= 0",
            name="ck_composition_snapshot_clips_non_negative_source_in",
        ),
        sa.CheckConstraint(
            "source_duration > 0",
            name="ck_composition_snapshot_clips_positive_duration",
        ),
        sa.CheckConstraint(
            "source_out > source_in",
            name="ck_composition_snapshot_clips_non_empty_range",
        ),
        sa.CheckConstraint(
            "source_out <= source_duration",
            name="ck_composition_snapshot_clips_range_within_source",
        ),
        sa.ForeignKeyConstraint(
            ["composition_snapshot_id"],
            ["composition_snapshots.composition_snapshot_id"],
            name="fk_composition_snapshot_clips_snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["composition_snapshot_id", "snapshot_track_id"],
            [
                "composition_snapshot_tracks.composition_snapshot_id",
                "composition_snapshot_tracks.snapshot_track_id",
            ],
            name="fk_composition_snapshot_clips_same_snapshot_track",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_version_id"],
            ["asset_versions.asset_version_id"],
            name="fk_composition_snapshot_clips_source_asset_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_clip_id", name="pk_composition_snapshot_clips"),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "canonical_clip_id",
            name="uq_composition_snapshot_clips_canonical_identity",
        ),
    )
    op.create_index(
        "ix_composition_snapshot_clips_timeline",
        "composition_snapshot_clips",
        ["snapshot_track_id", "timeline_start", "snapshot_clip_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_snapshot_clips_source_asset_version",
        "composition_snapshot_clips",
        ["source_asset_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """새 arrangement row만 제거하고 기존 SnapshotItem은 유지한다."""

    op.execute(sa.text("DELETE FROM composition_snapshot_clips"))
    op.execute(sa.text("DELETE FROM composition_clips"))
    op.drop_index(
        "ix_composition_snapshot_clips_source_asset_version",
        table_name="composition_snapshot_clips",
    )
    op.drop_index(
        "ix_composition_snapshot_clips_timeline",
        table_name="composition_snapshot_clips",
    )
    op.drop_table("composition_snapshot_clips")
    op.drop_index(
        "ix_composition_snapshot_tracks_order",
        table_name="composition_snapshot_tracks",
    )
    op.drop_table("composition_snapshot_tracks")
    op.drop_index("ix_composition_clips_split_parent", table_name="composition_clips")
    op.drop_index("ix_composition_clips_deleted_at", table_name="composition_clips")
    op.drop_index(
        "ix_composition_clips_source_asset_version",
        table_name="composition_clips",
    )
    op.drop_index("ix_composition_clips_active_timeline", table_name="composition_clips")
    op.drop_table("composition_clips")
    op.drop_index("ix_composition_tracks_active_order", table_name="composition_tracks")
    op.drop_index("ix_composition_tracks_deleted_at", table_name="composition_tracks")
    op.drop_index("uq_composition_tracks_active_order", table_name="composition_tracks")
    op.drop_table("composition_tracks")
    op.drop_index(
        "ix_working_compositions_base_snapshot",
        table_name="working_compositions",
    )
    op.drop_table("working_compositions")
