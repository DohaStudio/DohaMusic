"""Lyrics documents for synchronous local providers.

Revision ID: 20260729_0005
Revises: 20260729_0004
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lyrics_documents",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column("mood", sa.String(100), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lyrics_documents_language", "lyrics_documents", ["language"])
    op.create_index("ix_lyrics_documents_provider", "lyrics_documents", ["provider"])
    op.create_index("ix_lyrics_documents_status", "lyrics_documents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lyrics_documents_status", table_name="lyrics_documents")
    op.drop_index("ix_lyrics_documents_provider", table_name="lyrics_documents")
    op.drop_index("ix_lyrics_documents_language", table_name="lyrics_documents")
    op.drop_table("lyrics_documents")
