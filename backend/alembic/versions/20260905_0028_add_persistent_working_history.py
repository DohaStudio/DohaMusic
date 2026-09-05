"""Add persistent WorkingComposition product history.

Revision ID: 20260905_0028
Revises: 20260905_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0028"
down_revision: str | Sequence[str] | None = "20260905_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "working_composition_history_states",
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cursor >= 0", name="ck_working_history_state_cursor"),
        sa.ForeignKeyConstraint(
            ["working_composition_id"],
            ["working_compositions.working_composition_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("working_composition_id"),
    )
    op.create_table(
        "working_composition_history_entries",
        sa.Column("history_entry_id", sa.Uuid(), nullable=False),
        sa.Column("working_composition_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("command_type", sa.String(length=32), nullable=False),
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=False),
        sa.Column("after_state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_working_history_entry_sequence"),
        sa.ForeignKeyConstraint(
            ["working_composition_id"],
            ["working_compositions.working_composition_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("history_entry_id"),
        sa.UniqueConstraint(
            "working_composition_id", "sequence", name="uq_working_history_sequence"
        ),
    )
    op.create_index(
        "ix_working_history_cursor",
        "working_composition_history_entries",
        ["working_composition_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_working_history_cursor", table_name="working_composition_history_entries")
    op.drop_table("working_composition_history_entries")
    op.drop_table("working_composition_history_states")
