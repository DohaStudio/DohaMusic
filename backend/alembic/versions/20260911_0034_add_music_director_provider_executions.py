"""Add durable Music Director provider execution intents."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0034"
down_revision = "20260911_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_director_provider_executions",
        sa.Column("provider_execution_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=256), nullable=True),
        sa.Column("client_execution_key", sa.String(length=64), nullable=False),
        sa.Column("external_job_id", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 0", name="ck_music_director_provider_executions_version"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("provider_execution_id"),
        sa.UniqueConstraint("job_id", name="uq_music_director_provider_executions_job"),
        sa.UniqueConstraint(
            "client_execution_key", name="uq_music_director_provider_executions_client_key"
        ),
        sa.UniqueConstraint(
            "provider_id",
            "external_job_id",
            name="uq_music_director_provider_executions_external_identity",
        ),
    )
    op.create_index(
        "ix_music_director_provider_executions_provider_id",
        "music_director_provider_executions",
        ["provider_id"],
    )
    op.create_index(
        "ix_music_director_provider_executions_status",
        "music_director_provider_executions",
        ["status"],
    )
    op.create_index(
        "ix_music_director_provider_executions_recovery",
        "music_director_provider_executions",
        ["status", "updated_at", "provider_execution_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.scalar(sa.text("SELECT COUNT(*) FROM music_director_provider_executions"))
    if count:
        raise RuntimeError(
            "0034 downgrade is blocked while provider execution recovery authority exists"
        )
    op.drop_index(
        "ix_music_director_provider_executions_recovery",
        table_name="music_director_provider_executions",
    )
    op.drop_index(
        "ix_music_director_provider_executions_status",
        table_name="music_director_provider_executions",
    )
    op.drop_index(
        "ix_music_director_provider_executions_provider_id",
        table_name="music_director_provider_executions",
    )
    op.drop_table("music_director_provider_executions")
