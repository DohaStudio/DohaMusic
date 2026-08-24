"""Workspace 목표 Entity 21개 Table을 additive하게 추가한다.

Revision ID: 20260806_0012
Revises: 20260801_0011
Create Date: 2026-08-06 12:11:02.293099
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0012"
down_revision: str | None = "20260801_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 Runtime schema를 변경하지 않고 Workspace Table만 추가한다."""
    op.create_table(
        "asset_versions",
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_origin", sa.String(), nullable=False),
        sa.Column("parent_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("processing_chain_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.String(), nullable=True),
        sa.Column("model_manifest_id", sa.String(), nullable=True),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_asset_versions_positive_number"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parent_asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["processing_chain_id"],
            ["processing_chains.processing_chain_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("asset_version_id"),
        sa.UniqueConstraint("asset_id", "version_number", name="uq_asset_versions_number"),
    )
    op.create_index(
        op.f("ix_asset_versions_asset_id"), "asset_versions", ["asset_id"], unique=False
    )
    op.create_index(
        op.f("ix_asset_versions_created_by"),
        "asset_versions",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_versions_model_manifest_id"),
        "asset_versions",
        ["model_manifest_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_versions_parent_asset_version_id"),
        "asset_versions",
        ["parent_asset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_versions_processing_chain_id"),
        "asset_versions",
        ["processing_chain_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_versions_provider_id"),
        "asset_versions",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_versions_version_origin"),
        "asset_versions",
        ["version_origin"],
        unique=False,
    )
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(
                "lyrics",
                "music",
                "vocal",
                "stem",
                "recording",
                "mix",
                "export",
                name="workspace_asset_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("selected_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("lifecycle_status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["selected_asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.UniqueConstraint("selected_asset_version_id"),
    )
    op.create_index(op.f("ix_assets_asset_type"), "assets", ["asset_type"], unique=False)
    op.create_index(op.f("ix_assets_deleted_at"), "assets", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_assets_lifecycle_status"), "assets", ["lifecycle_status"], unique=False
    )
    op.create_index(op.f("ix_assets_owner_id"), "assets", ["owner_id"], unique=False)
    op.create_index(op.f("ix_assets_workspace_id"), "assets", ["workspace_id"], unique=False)
    op.create_table(
        "processing_chains",
        sa.Column("processing_chain_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("chain_version", sa.String(), nullable=False),
        sa.Column("chain_checksum", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("processing_chain_id"),
        sa.UniqueConstraint("chain_checksum"),
        sa.UniqueConstraint("name", "chain_version", name="uq_processing_chains_version"),
    )
    op.create_index(
        op.f("ix_processing_chains_created_by"),
        "processing_chains",
        ["created_by"],
        unique=False,
    )
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lifecycle_status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_index(op.f("ix_workspaces_deleted_at"), "workspaces", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_workspaces_lifecycle_status"),
        "workspaces",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index(op.f("ix_workspaces_owner_id"), "workspaces", ["owner_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_kind", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_algorithm", sa.String(), nullable=False),
        sa.Column("artifact_checksum", sa.String(), nullable=False),
        sa.Column("producer_type", sa.String(), nullable=False),
        sa.Column("producer_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("retention_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("artifact_id"),
    )
    op.create_index(
        op.f("ix_artifacts_artifact_checksum"),
        "artifacts",
        ["artifact_checksum"],
        unique=False,
    )
    op.create_index(
        op.f("ix_artifacts_artifact_kind"), "artifacts", ["artifact_kind"], unique=False
    )
    op.create_index(
        op.f("ix_artifacts_asset_version_id"),
        "artifacts",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_artifacts_checksum_size",
        "artifacts",
        ["checksum_algorithm", "artifact_checksum", "size_bytes"],
        unique=False,
    )
    op.create_index(op.f("ix_artifacts_media_type"), "artifacts", ["media_type"], unique=False)
    op.create_index(op.f("ix_artifacts_producer_id"), "artifacts", ["producer_id"], unique=False)
    op.create_index(
        op.f("ix_artifacts_producer_type"), "artifacts", ["producer_type"], unique=False
    )
    op.create_index(
        op.f("ix_artifacts_retention_status"),
        "artifacts",
        ["retention_status"],
        unique=False,
    )
    op.create_index(op.f("ix_artifacts_run_id"), "artifacts", ["run_id"], unique=False)
    op.create_table(
        "asset_relations",
        sa.Column("relation_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("target_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("target_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((source_asset_id IS NOT NULL AND target_asset_id IS NOT NULL AND "
            "source_asset_version_id IS NULL AND target_asset_version_id IS NULL AND "
            "source_asset_id <> target_asset_id) OR (source_asset_id IS NULL AND "
            "target_asset_id IS NULL AND source_asset_version_id IS NOT NULL AND "
            "target_asset_version_id IS NOT NULL AND "
            "source_asset_version_id <> target_asset_version_id))",
            name="ck_asset_relations_exact_pair",
        ),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["target_asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("relation_id"),
        sa.UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relation_type",
            name="uq_asset_relations_asset_pair",
        ),
        sa.UniqueConstraint(
            "source_asset_version_id",
            "target_asset_version_id",
            "relation_type",
            name="uq_asset_relations_version_pair",
        ),
    )
    op.create_index(
        op.f("ix_asset_relations_relation_type"),
        "asset_relations",
        ["relation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_relations_source_asset_id"),
        "asset_relations",
        ["source_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_relations_source_asset_version_id"),
        "asset_relations",
        ["source_asset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_relations_target_asset_id"),
        "asset_relations",
        ["target_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_relations_target_asset_version_id"),
        "asset_relations",
        ["target_asset_version_id"],
        unique=False,
    )
    op.create_table(
        "comments",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("comment_id"),
    )
    op.create_index(
        op.f("ix_comments_asset_version_id"),
        "comments",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_comments_created_by"), "comments", ["created_by"], unique=False)
    op.create_index(op.f("ix_comments_deleted_at"), "comments", ["deleted_at"], unique=False)
    op.create_index(
        "ix_comments_version_created",
        "comments",
        ["asset_version_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "favorites",
        sa.Column("favorite_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("favorite_id"),
        sa.UniqueConstraint("workspace_id", "asset_id", name="uq_favorites_workspace_asset"),
    )
    op.create_index(op.f("ix_favorites_asset_id"), "favorites", ["asset_id"], unique=False)
    op.create_index(op.f("ix_favorites_deleted_at"), "favorites", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_favorites_workspace_id"), "favorites", ["workspace_id"], unique=False)
    op.create_table(
        "history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(op.f("ix_history_action"), "history", ["action"], unique=False)
    op.create_index(op.f("ix_history_actor_id"), "history", ["actor_id"], unique=False)
    op.create_index(
        "ix_history_entity_created",
        "history",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_history_entity_id"), "history", ["entity_id"], unique=False)
    op.create_index(op.f("ix_history_entity_type"), "history", ["entity_type"], unique=False)
    op.create_index(
        "ix_history_workspace_created",
        "history",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_history_workspace_id"), "history", ["workspace_id"], unique=False)
    op.create_table(
        "music_projects",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lifecycle_status", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.create_index(
        op.f("ix_music_projects_created_by"),
        "music_projects",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_music_projects_deleted_at"),
        "music_projects",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_music_projects_lifecycle_status"),
        "music_projects",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index(op.f("ix_music_projects_title"), "music_projects", ["title"], unique=False)
    op.create_index(
        op.f("ix_music_projects_workspace_id"),
        "music_projects",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "processing_steps",
        sa.Column("processing_step_id", sa.Uuid(), nullable=False),
        sa.Column("processing_chain_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("step_order >= 1", name="ck_processing_steps_positive_order"),
        sa.ForeignKeyConstraint(
            ["processing_chain_id"],
            ["processing_chains.processing_chain_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("processing_step_id"),
        sa.UniqueConstraint(
            "processing_chain_id", "step_order", name="uq_processing_steps_chain_order"
        ),
    )
    op.create_index(
        op.f("ix_processing_steps_processing_chain_id"),
        "processing_steps",
        ["processing_chain_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_processing_steps_step_type"),
        "processing_steps",
        ["step_type"],
        unique=False,
    )
    op.create_table(
        "recording_enrollments",
        sa.Column("recording_enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("recording_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("consent_policy_version", sa.String(), nullable=False),
        sa.Column("consent_evidence_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recording_asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("recording_enrollment_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "recording_asset_version_id",
            "consent_policy_version",
            name="uq_recording_enrollments_consent",
        ),
    )
    op.create_index(
        op.f("ix_recording_enrollments_consent_evidence_id"),
        "recording_enrollments",
        ["consent_evidence_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_consent_policy_version"),
        "recording_enrollments",
        ["consent_policy_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_created_by"),
        "recording_enrollments",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_deleted_at"),
        "recording_enrollments",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_recording_asset_version_id"),
        "recording_enrollments",
        ["recording_asset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_status"),
        "recording_enrollments",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recording_enrollments_workspace_id"),
        "recording_enrollments",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "tags",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("tag_id"),
        sa.UniqueConstraint("asset_id", "name", name="uq_tags_asset_name"),
    )
    op.create_index(op.f("ix_tags_asset_id"), "tags", ["asset_id"], unique=False)
    op.create_index(op.f("ix_tags_created_by"), "tags", ["created_by"], unique=False)
    op.create_index(op.f("ix_tags_deleted_at"), "tags", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=False)
    op.create_table(
        "composition_snapshots",
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("processing_chain_id", sa.Uuid(), nullable=True),
        sa.Column("mix_settings_snapshot", sa.JSON(), nullable=False),
        sa.Column("provider_versions", sa.JSON(), nullable=False),
        sa.Column("model_manifest_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "snapshot_version >= 1", name="ck_composition_snapshots_positive_version"
        ),
        sa.ForeignKeyConstraint(
            ["processing_chain_id"],
            ["processing_chains.processing_chain_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["music_projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("composition_snapshot_id"),
        sa.UniqueConstraint(
            "project_id", "snapshot_version", name="uq_composition_snapshots_version"
        ),
    )
    op.create_index(
        op.f("ix_composition_snapshots_created_by"),
        "composition_snapshots",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_composition_snapshots_processing_chain_id"),
        "composition_snapshots",
        ["processing_chain_id"],
        unique=False,
    )
    op.create_index(
        "ix_composition_snapshots_project_created",
        "composition_snapshots",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_composition_snapshots_project_id"),
        "composition_snapshots",
        ["project_id"],
        unique=False,
    )
    op.create_table(
        "project_assets",
        sa.Column("project_asset_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["music_projects.project_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_asset_id"),
        sa.UniqueConstraint("project_id", "asset_id", name="uq_project_assets_project_asset"),
    )
    op.create_index(
        op.f("ix_project_assets_asset_id"), "project_assets", ["asset_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_assets_deleted_at"),
        "project_assets",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_assets_project_id"),
        "project_assets",
        ["project_id"],
        unique=False,
    )
    op.create_index(op.f("ix_project_assets_role"), "project_assets", ["role"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="workspace_job_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(), nullable=True),
        sa.Column("api_contract_version", sa.String(), nullable=False),
        sa.Column("model_manifest_id", sa.String(), nullable=True),
        sa.Column("progress_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column("retry_of_job_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("error_details_id", sa.String(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="ck_jobs_progress_percent",
        ),
        sa.ForeignKeyConstraint(
            ["composition_snapshot_id"],
            ["composition_snapshots.composition_snapshot_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["music_projects.project_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        op.f("ix_jobs_api_contract_version"),
        "jobs",
        ["api_contract_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jobs_composition_snapshot_id"),
        "jobs",
        ["composition_snapshot_id"],
        unique=False,
    )
    op.create_index(op.f("ix_jobs_error_code"), "jobs", ["error_code"], unique=False)
    op.create_index(op.f("ix_jobs_error_details_id"), "jobs", ["error_details_id"], unique=False)
    op.create_index(op.f("ix_jobs_job_type"), "jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_jobs_model_manifest_id"), "jobs", ["model_manifest_id"], unique=False)
    op.create_index("ix_jobs_project_created", "jobs", ["project_id", "created_at"], unique=False)
    op.create_index(op.f("ix_jobs_project_id"), "jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_jobs_provider_id"), "jobs", ["provider_id"], unique=False)
    op.create_index(op.f("ix_jobs_requested_by"), "jobs", ["requested_by"], unique=False)
    op.create_index(op.f("ix_jobs_retry_of_job_id"), "jobs", ["retry_of_job_id"], unique=False)
    op.create_index(op.f("ix_jobs_stage"), "jobs", ["stage"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"], unique=False)
    op.create_table(
        "snapshot_items",
        sa.Column("snapshot_item_id", sa.Uuid(), nullable=False),
        sa.Column("composition_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("item_role", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["composition_snapshot_id"],
            ["composition_snapshots.composition_snapshot_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_item_id"),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "asset_version_id",
            "item_role",
            name="uq_snapshot_items_version_role",
        ),
        sa.UniqueConstraint(
            "composition_snapshot_id",
            "item_role",
            "sort_order",
            name="uq_snapshot_items_role_order",
        ),
    )
    op.create_index(
        op.f("ix_snapshot_items_asset_version_id"),
        "snapshot_items",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_items_composition_snapshot_id"),
        "snapshot_items",
        ["composition_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_items_item_role"),
        "snapshot_items",
        ["item_role"],
        unique=False,
    )
    op.create_table(
        "job_inputs",
        sa.Column("job_input_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("input_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(asset_version_id IS NOT NULL AND artifact_id IS NULL) OR "
            "(asset_version_id IS NULL AND artifact_id IS NOT NULL)",
            name="ck_job_inputs_exact_source",
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("job_input_id"),
        sa.UniqueConstraint("job_id", "input_order", name="uq_job_inputs_order"),
    )
    op.create_index(op.f("ix_job_inputs_artifact_id"), "job_inputs", ["artifact_id"], unique=False)
    op.create_index(
        op.f("ix_job_inputs_asset_version_id"),
        "job_inputs",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_job_inputs_job_id"), "job_inputs", ["job_id"], unique=False)
    op.create_table(
        "job_outputs",
        sa.Column("job_output_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("output_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(asset_version_id IS NOT NULL AND artifact_id IS NULL) OR "
            "(asset_version_id IS NULL AND artifact_id IS NOT NULL)",
            name="ck_job_outputs_exact_target",
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.artifact_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("job_output_id"),
        sa.UniqueConstraint("job_id", "output_order", name="uq_job_outputs_order"),
    )
    op.create_index(
        op.f("ix_job_outputs_artifact_id"), "job_outputs", ["artifact_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_outputs_asset_version_id"),
        "job_outputs",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_job_outputs_job_id"), "job_outputs", ["job_id"], unique=False)
    op.create_table(
        "model_usages",
        sa.Column("model_usage_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("model_manifest_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("checkpoint_version", sa.String(), nullable=True),
        sa.Column("api_contract_version", sa.String(), nullable=False),
        sa.Column("license_status", sa.String(), nullable=False),
        sa.Column("commercial_usage_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("model_usage_id"),
        sa.UniqueConstraint(
            "job_id",
            "model_manifest_id",
            "asset_version_id",
            name="uq_model_usages_job_manifest_version",
        ),
    )
    op.create_index(
        op.f("ix_model_usages_api_contract_version"),
        "model_usages",
        ["api_contract_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_usages_asset_version_id"),
        "model_usages",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_usages_commercial_usage_status"),
        "model_usages",
        ["commercial_usage_status"],
        unique=False,
    )
    op.create_index(op.f("ix_model_usages_job_id"), "model_usages", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_model_usages_license_status"),
        "model_usages",
        ["license_status"],
        unique=False,
    )
    op.create_index(op.f("ix_model_usages_model_id"), "model_usages", ["model_id"], unique=False)
    op.create_index(
        op.f("ix_model_usages_model_manifest_id"),
        "model_usages",
        ["model_manifest_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_usages_provider_id"),
        "model_usages",
        ["provider_id"],
        unique=False,
    )
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("recording_enrollment_id", sa.Uuid(), nullable=True),
        sa.Column("model_usage_id", sa.Uuid(), nullable=True),
        sa.Column("usage_purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN asset_version_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN recording_enrollment_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN model_usage_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_approvals_exact_target",
        ),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.asset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_usage_id"], ["model_usages.model_usage_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recording_enrollment_id"],
            ["recording_enrollments.recording_enrollment_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    op.create_index(op.f("ix_approvals_approved_by"), "approvals", ["approved_by"], unique=False)
    op.create_index(
        op.f("ix_approvals_asset_version_id"),
        "approvals",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_approvals_decided_at"), "approvals", ["decided_at"], unique=False)
    op.create_index(op.f("ix_approvals_evidence_id"), "approvals", ["evidence_id"], unique=False)
    op.create_index(
        op.f("ix_approvals_model_usage_id"),
        "approvals",
        ["model_usage_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approvals_recording_enrollment_id"),
        "approvals",
        ["recording_enrollment_id"],
        unique=False,
    )
    op.create_index(op.f("ix_approvals_status"), "approvals", ["status"], unique=False)
    op.create_index(
        op.f("ix_approvals_usage_purpose"), "approvals", ["usage_purpose"], unique=False
    )


def downgrade() -> None:
    """Workspace Table만 FK 의존성의 역순으로 제거한다."""
    op.drop_index(op.f("ix_approvals_usage_purpose"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_status"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_recording_enrollment_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_model_usage_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_evidence_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_decided_at"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_asset_version_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_approved_by"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_index(op.f("ix_model_usages_provider_id"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_model_manifest_id"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_model_id"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_license_status"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_job_id"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_commercial_usage_status"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_asset_version_id"), table_name="model_usages")
    op.drop_index(op.f("ix_model_usages_api_contract_version"), table_name="model_usages")
    op.drop_table("model_usages")
    op.drop_index(op.f("ix_job_outputs_job_id"), table_name="job_outputs")
    op.drop_index(op.f("ix_job_outputs_asset_version_id"), table_name="job_outputs")
    op.drop_index(op.f("ix_job_outputs_artifact_id"), table_name="job_outputs")
    op.drop_table("job_outputs")
    op.drop_index(op.f("ix_job_inputs_job_id"), table_name="job_inputs")
    op.drop_index(op.f("ix_job_inputs_asset_version_id"), table_name="job_inputs")
    op.drop_index(op.f("ix_job_inputs_artifact_id"), table_name="job_inputs")
    op.drop_table("job_inputs")
    op.drop_index(op.f("ix_snapshot_items_item_role"), table_name="snapshot_items")
    op.drop_index(op.f("ix_snapshot_items_composition_snapshot_id"), table_name="snapshot_items")
    op.drop_index(op.f("ix_snapshot_items_asset_version_id"), table_name="snapshot_items")
    op.drop_table("snapshot_items")
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_stage"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_retry_of_job_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_requested_by"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_provider_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_project_id"), table_name="jobs")
    op.drop_index("ix_jobs_project_created", table_name="jobs")
    op.drop_index(op.f("ix_jobs_model_manifest_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_job_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_error_details_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_error_code"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_composition_snapshot_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_api_contract_version"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_project_assets_role"), table_name="project_assets")
    op.drop_index(op.f("ix_project_assets_project_id"), table_name="project_assets")
    op.drop_index(op.f("ix_project_assets_deleted_at"), table_name="project_assets")
    op.drop_index(op.f("ix_project_assets_asset_id"), table_name="project_assets")
    op.drop_table("project_assets")
    op.drop_index(op.f("ix_composition_snapshots_project_id"), table_name="composition_snapshots")
    op.drop_index("ix_composition_snapshots_project_created", table_name="composition_snapshots")
    op.drop_index(
        op.f("ix_composition_snapshots_processing_chain_id"),
        table_name="composition_snapshots",
    )
    op.drop_index(op.f("ix_composition_snapshots_created_by"), table_name="composition_snapshots")
    op.drop_table("composition_snapshots")
    op.drop_index(op.f("ix_tags_name"), table_name="tags")
    op.drop_index(op.f("ix_tags_deleted_at"), table_name="tags")
    op.drop_index(op.f("ix_tags_created_by"), table_name="tags")
    op.drop_index(op.f("ix_tags_asset_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(
        op.f("ix_recording_enrollments_workspace_id"),
        table_name="recording_enrollments",
    )
    op.drop_index(op.f("ix_recording_enrollments_status"), table_name="recording_enrollments")
    op.drop_index(
        op.f("ix_recording_enrollments_recording_asset_version_id"),
        table_name="recording_enrollments",
    )
    op.drop_index(op.f("ix_recording_enrollments_deleted_at"), table_name="recording_enrollments")
    op.drop_index(op.f("ix_recording_enrollments_created_by"), table_name="recording_enrollments")
    op.drop_index(
        op.f("ix_recording_enrollments_consent_policy_version"),
        table_name="recording_enrollments",
    )
    op.drop_index(
        op.f("ix_recording_enrollments_consent_evidence_id"),
        table_name="recording_enrollments",
    )
    op.drop_table("recording_enrollments")
    op.drop_index(op.f("ix_processing_steps_step_type"), table_name="processing_steps")
    op.drop_index(op.f("ix_processing_steps_processing_chain_id"), table_name="processing_steps")
    op.drop_table("processing_steps")
    op.drop_index(op.f("ix_music_projects_workspace_id"), table_name="music_projects")
    op.drop_index(op.f("ix_music_projects_title"), table_name="music_projects")
    op.drop_index(op.f("ix_music_projects_lifecycle_status"), table_name="music_projects")
    op.drop_index(op.f("ix_music_projects_deleted_at"), table_name="music_projects")
    op.drop_index(op.f("ix_music_projects_created_by"), table_name="music_projects")
    op.drop_table("music_projects")
    op.drop_index(op.f("ix_history_workspace_id"), table_name="history")
    op.drop_index("ix_history_workspace_created", table_name="history")
    op.drop_index(op.f("ix_history_entity_type"), table_name="history")
    op.drop_index(op.f("ix_history_entity_id"), table_name="history")
    op.drop_index("ix_history_entity_created", table_name="history")
    op.drop_index(op.f("ix_history_actor_id"), table_name="history")
    op.drop_index(op.f("ix_history_action"), table_name="history")
    op.drop_table("history")
    op.drop_index(op.f("ix_favorites_workspace_id"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_deleted_at"), table_name="favorites")
    op.drop_index(op.f("ix_favorites_asset_id"), table_name="favorites")
    op.drop_table("favorites")
    op.drop_index("ix_comments_version_created", table_name="comments")
    op.drop_index(op.f("ix_comments_deleted_at"), table_name="comments")
    op.drop_index(op.f("ix_comments_created_by"), table_name="comments")
    op.drop_index(op.f("ix_comments_asset_version_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(op.f("ix_asset_relations_target_asset_version_id"), table_name="asset_relations")
    op.drop_index(op.f("ix_asset_relations_target_asset_id"), table_name="asset_relations")
    op.drop_index(op.f("ix_asset_relations_source_asset_version_id"), table_name="asset_relations")
    op.drop_index(op.f("ix_asset_relations_source_asset_id"), table_name="asset_relations")
    op.drop_index(op.f("ix_asset_relations_relation_type"), table_name="asset_relations")
    op.drop_table("asset_relations")
    op.drop_index(op.f("ix_artifacts_run_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_retention_status"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_producer_type"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_producer_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_media_type"), table_name="artifacts")
    op.drop_index("ix_artifacts_checksum_size", table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_asset_version_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_artifact_kind"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_artifact_checksum"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index(op.f("ix_workspaces_owner_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_lifecycle_status"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_deleted_at"), table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index(op.f("ix_processing_chains_created_by"), table_name="processing_chains")
    op.drop_table("processing_chains")
    op.drop_index(op.f("ix_assets_workspace_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_owner_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_lifecycle_status"), table_name="assets")
    op.drop_index(op.f("ix_assets_deleted_at"), table_name="assets")
    op.drop_index(op.f("ix_assets_asset_type"), table_name="assets")
    op.drop_table("assets")
    op.drop_index(op.f("ix_asset_versions_version_origin"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_provider_id"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_processing_chain_id"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_parent_asset_version_id"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_model_manifest_id"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_created_by"), table_name="asset_versions")
    op.drop_index(op.f("ix_asset_versions_asset_id"), table_name="asset_versions")
    op.drop_table("asset_versions")
