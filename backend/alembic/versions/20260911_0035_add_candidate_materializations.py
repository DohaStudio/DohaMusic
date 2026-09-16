"""Add durable Music Director candidate materialization intents."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0035"
down_revision = "20260911_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_director_candidate_materializations",
        sa.Column("materialization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("materialization_key", sa.String(64), nullable=False),
        sa.Column("proposal_digest", sa.String(64), nullable=False),
        sa.Column("planned_run_id", sa.Uuid(), nullable=False),
        sa.Column("planned_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("planned_asset_id", sa.Uuid(), nullable=False),
        sa.Column("planned_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("planned_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("storage_domain", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ordinal >= 0 AND ordinal < 4", name="ck_md_materializations_ordinal"),
        sa.CheckConstraint("length(proposal_digest) = 64", name="ck_md_materializations_digest"),
        sa.CheckConstraint("version >= 0", name="ck_md_materializations_version"),
        sa.CheckConstraint(
            "status IN ('intended', 'published', 'completed', 'reconciliation_required')",
            name="ck_md_materializations_status",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("materialization_id"),
        sa.UniqueConstraint("job_id", "ordinal", name="uq_md_materializations_job_ordinal"),
        sa.UniqueConstraint("materialization_key", name="uq_md_materializations_key"),
        sa.UniqueConstraint("planned_candidate_id", name="uq_md_materializations_candidate"),
        sa.UniqueConstraint("planned_asset_id", name="uq_md_materializations_asset"),
        sa.UniqueConstraint("planned_asset_version_id", name="uq_md_materializations_version"),
        sa.UniqueConstraint("planned_artifact_id", name="uq_md_materializations_artifact"),
        sa.UniqueConstraint("storage_domain", "storage_key", name="uq_md_materializations_storage"),
    )
    op.create_index(
        "ix_md_materializations_recovery",
        "music_director_candidate_materializations",
        ["status", "updated_at", "materialization_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.scalar(
        sa.text("SELECT COUNT(*) FROM music_director_candidate_materializations")
    )
    if count:
        raise RuntimeError("0035 downgrade is blocked while materialization authority exists")
    op.drop_index(
        "ix_md_materializations_recovery",
        table_name="music_director_candidate_materializations",
    )
    op.drop_table("music_director_candidate_materializations")
