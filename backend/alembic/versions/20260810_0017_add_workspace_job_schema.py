"""Workspace Job scope, role, claim·lease Column과 Index를 추가한다.

Revision ID: 20260810_0017
Revises: 20260809_0016
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0017"
down_revision: str | None = "20260809_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PUBLIC_KEYSET_INDEXES = (
    (
        "ix_jobs_workspace_keyset",
        ("workspace_id", "created_at", "job_id"),
    ),
    (
        "ix_jobs_workspace_project_keyset",
        ("workspace_id", "project_id", "created_at", "job_id"),
    ),
    (
        "ix_jobs_workspace_status_keyset",
        ("workspace_id", "status", "created_at", "job_id"),
    ),
    (
        "ix_jobs_workspace_type_keyset",
        ("workspace_id", "job_type", "created_at", "job_id"),
    ),
)
WORKER_INDEXES = (
    (
        "ix_jobs_claim_queue",
        ("status", "cancel_requested_at", "created_at", "job_id"),
    ),
    (
        "ix_jobs_lease_recovery",
        ("status", "lease_expires_at", "job_id"),
    ),
)


def upgrade() -> None:
    """기존 Job row를 보존하며 Workspace scope와 실행 제어 기반을 추가한다."""

    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "ALTER TABLE jobs ADD COLUMN workspace_id CHAR(32) "
            "CONSTRAINT fk_jobs_workspace_id_workspaces "
            "REFERENCES workspaces (workspace_id) ON DELETE RESTRICT"
        )
    else:
        op.add_column("jobs", sa.Column("workspace_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            "fk_jobs_workspace_id_workspaces",
            "jobs",
            "workspaces",
            ["workspace_id"],
            ["workspace_id"],
            ondelete="RESTRICT",
        )
    op.add_column("jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("claim_token", sa.Uuid(), nullable=True))
    op.add_column("jobs", sa.Column("claimed_by", sa.String(128), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "ALTER TABLE jobs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0 "
            "CONSTRAINT ck_jobs_attempt_nonnegative CHECK (attempt >= 0)"
        )
    else:
        op.add_column(
            "jobs",
            sa.Column(
                "attempt",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.create_check_constraint(
            "ck_jobs_attempt_nonnegative",
            "jobs",
            "attempt >= 0",
        )
    op.add_column("job_inputs", sa.Column("input_role", sa.String(64)))
    op.add_column("job_outputs", sa.Column("output_role", sa.String(64)))

    connection.execute(
        sa.text(
            "UPDATE jobs SET workspace_id = ("
            "SELECT music_projects.workspace_id FROM music_projects "
            "WHERE music_projects.project_id = jobs.project_id"
            ") WHERE workspace_id IS NULL"
        )
    )
    unresolved = connection.execute(
        sa.text("SELECT count(*) FROM jobs WHERE workspace_id IS NULL")
    ).scalar_one()
    if unresolved:
        raise RuntimeError("Job.workspace_id를 Project에서 안전하게 backfill할 수 없습니다.")

    for index_name, columns in PUBLIC_KEYSET_INDEXES + WORKER_INDEXES:
        op.create_index(index_name, "jobs", list(columns), unique=False)

    if connection.dialect.name == "sqlite":
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        if violations:
            raise RuntimeError("Workspace Job Migration 후 FK 위반이 발견됐습니다.")


def downgrade() -> None:
    """이번 revision에서 추가한 Index와 Column만 제거한다."""

    connection = op.get_bind()

    for index_name, _ in reversed(PUBLIC_KEYSET_INDEXES + WORKER_INDEXES):
        op.drop_index(index_name, table_name="jobs")

    op.drop_column("jobs", "attempt")
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "claimed_by")
    op.drop_column("jobs", "claim_token")
    op.drop_column("jobs", "cancel_requested_at")
    op.drop_column("jobs", "workspace_id")
    op.drop_column("job_inputs", "input_role")
    op.drop_column("job_outputs", "output_role")

    if connection.dialect.name == "sqlite":
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        if violations:
            raise RuntimeError("Workspace Job downgrade 후 FK 위반이 발견됐습니다.")
