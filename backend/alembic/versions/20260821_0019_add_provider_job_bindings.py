"""Provider Job identity binding table을 추가한다.

Revision ID: 20260821_0019
Revises: 20260820_0018
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0019"
down_revision: str | None = "20260820_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 Job row backfill 없이 1:N Provider 실행 이력 table을 만든다."""

    op.create_table(
        "provider_job_bindings",
        sa.Column("provider_job_binding_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_job_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(128), nullable=False),
        sa.Column("provider_job_id", sa.String(256), nullable=False),
        sa.Column("retry_of_provider_job_id", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "retry_of_provider_job_id IS NULL OR retry_of_provider_job_id <> provider_job_id",
            name="ck_provider_job_bindings_no_self_retry",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_job_id"],
            ["jobs.job_id"],
            name="fk_provider_job_bindings_workspace_job_id_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id", "retry_of_provider_job_id"],
            [
                "provider_job_bindings.provider_id",
                "provider_job_bindings.provider_job_id",
            ],
            name="fk_provider_job_bindings_retry_identity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "provider_job_binding_id",
            name="pk_provider_job_bindings",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "provider_job_id",
            name="uq_provider_job_bindings_identity",
        ),
    )
    op.create_index(
        "ix_provider_job_bindings_workspace_history",
        "provider_job_bindings",
        ["workspace_job_id", "created_at", "provider_job_binding_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_job_bindings_provider_job_id",
        "provider_job_bindings",
        ["provider_job_id"],
        unique=False,
    )


def downgrade() -> None:
    """Provider Job binding history table만 제거한다."""

    # SQLite는 self-referencing FK가 있는 populated table의 DROP을 거부하므로
    # downgrade가 어차피 제거할 이력을 leaf부터 비운다.
    op.execute(
        sa.text("DELETE FROM provider_job_bindings WHERE retry_of_provider_job_id IS NOT NULL")
    )
    op.execute(sa.text("DELETE FROM provider_job_bindings"))
    op.drop_index(
        "ix_provider_job_bindings_provider_job_id",
        table_name="provider_job_bindings",
    )
    op.drop_index(
        "ix_provider_job_bindings_workspace_history",
        table_name="provider_job_bindings",
    )
    op.drop_table("provider_job_bindings")
