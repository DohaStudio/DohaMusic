"""Clip linear Fade canonical persistence를 추가한다.

Revision ID: 20260903_0026
Revises: 20260830_0025
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0026"
down_revision: str | Sequence[str] | None = "20260830_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    (
        "composition_clips",
        "fade_in",
        "fade_out",
        "source_out - source_in",
        "ck_composition_clips_fade_in_non_negative",
        "ck_composition_clips_fade_range",
    ),
    (
        "composition_snapshot_clips",
        "fade_in",
        "fade_out",
        "source_out - source_in",
        "ck_composition_snapshot_clips_fade_in_non_negative",
        "ck_composition_snapshot_clips_fade_range",
    ),
    (
        "working_preview_render_clips",
        "fade_in_us",
        "fade_out_us",
        "source_out_us - source_in_us",
        "ck_working_preview_clip_fade_in_non_negative",
        "ck_working_preview_clip_fade_range",
    ),
)


def upgrade() -> None:
    """기존 Clip을 zero Fade로 보존하며 세 canonical 경계에 Fade를 추가한다."""

    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for table_name, fade_in, fade_out, duration, in_constraint, range_constraint in TABLES:
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {fade_in} BIGINT NOT NULL DEFAULT 0 "
                f"CONSTRAINT {in_constraint} CHECK ({fade_in} >= 0)"
            )
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {fade_out} BIGINT NOT NULL DEFAULT 0 "
                f"CONSTRAINT {range_constraint} "
                f"CHECK ({fade_out} >= 0 AND {fade_in} + {fade_out} <= {duration})"
            )
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        if violations:
            raise RuntimeError("Clip Fade Migration 후 FK 위반이 발견됐습니다.")
        return

    for table_name, fade_in, fade_out, duration, in_constraint, range_constraint in TABLES:
        op.add_column(
            table_name,
            sa.Column(fade_in, sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        )
        op.add_column(
            table_name,
            sa.Column(fade_out, sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        )
        op.create_check_constraint(in_constraint, table_name, f"{fade_in} >= 0")
        op.create_check_constraint(
            range_constraint,
            table_name,
            f"{fade_out} >= 0 AND {fade_in} + {fade_out} <= {duration}",
        )


def downgrade() -> None:
    """Clip Fade column과 전용 CHECK만 역순으로 제거한다."""

    connection = op.get_bind()
    for table_name, fade_in, fade_out, _duration, in_constraint, range_constraint in reversed(
        TABLES
    ):
        if connection.dialect.name != "sqlite":
            op.drop_constraint(range_constraint, table_name, type_="check")
            op.drop_constraint(in_constraint, table_name, type_="check")
        op.drop_column(table_name, fade_out)
        op.drop_column(table_name, fade_in)
