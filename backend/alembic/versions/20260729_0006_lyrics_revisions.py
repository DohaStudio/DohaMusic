"""Preserve lyrics revisions as immutable document versions.

Revision ID: 20260729_0006
Revises: 20260729_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0006"
down_revision: str | None = "20260729_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lyrics_documents") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("revision_instruction", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("result_hash", sa.String(64), nullable=True))
        batch_op.create_foreign_key(
            "fk_lyrics_documents_parent_id",
            "lyrics_documents",
            ["parent_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_lyrics_documents_parent_id", ["parent_id"])


def downgrade() -> None:
    with op.batch_alter_table("lyrics_documents") as batch_op:
        batch_op.drop_index("ix_lyrics_documents_parent_id")
        batch_op.drop_constraint("fk_lyrics_documents_parent_id", type_="foreignkey")
        batch_op.drop_column("result_hash")
        batch_op.drop_column("source_hash")
        batch_op.drop_column("revision_instruction")
        batch_op.drop_column("version")
        batch_op.drop_column("parent_id")
