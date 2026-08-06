"""Add projects and connect pipeline jobs.

Revision ID: 20260731_0008
Revises: 20260731_0007
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20260731_0008"
down_revision = "20260731_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_title", "projects", ["title"])
    default_id = "00000000-0000-0000-0000-000000000001"
    projects = sa.table(
        "projects",
        sa.column("id", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        projects,
        [
            {
                "id": default_id,
                "title": "Default Project",
                "description": None,
                "is_default": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    with op.batch_alter_table("pipeline_jobs") as batch:
        batch.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_pipeline_jobs_project_id", ["project_id"])
        batch.create_foreign_key(
            "fk_pipeline_jobs_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text("UPDATE pipeline_jobs SET project_id = :project_id").bindparams(
            project_id=default_id
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("pipeline_jobs") as batch:
        batch.drop_constraint(
            "fk_pipeline_jobs_project_id_projects", type_="foreignkey"
        )
        batch.drop_index("ix_pipeline_jobs_project_id")
        batch.drop_column("project_id")
    op.drop_index("ix_projects_title", table_name="projects")
    op.drop_table("projects")
