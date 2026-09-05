"""Clip static Gain canonical persistence를 추가한다.

Revision ID: 20260830_0025
Revises: 20260828_0024
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0025"
down_revision: str | Sequence[str] | None = "20260828_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    ("composition_clips", "ck_composition_clips_gain_db_range"),
    ("composition_snapshot_clips", "ck_composition_snapshot_clips_gain_db_range"),
    ("working_preview_render_clips", "ck_working_preview_clip_gain_db_range"),
)


def upgrade() -> None:
    """기존 Clip 의미를 0.00 dB로 보존하며 세 manifest에 Gain을 추가한다."""

    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for table_name, constraint_name in TABLES:
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN gain_db NUMERIC(5, 2) "
                f"NOT NULL DEFAULT 0.00 CONSTRAINT {constraint_name} "
                "CHECK (gain_db >= -24.00 AND gain_db <= 24.00)"
            )
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        if violations:
            raise RuntimeError("Clip Gain Migration 후 FK 위반이 발견됐습니다.")
        return

    for table_name, constraint_name in TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "gain_db",
                sa.Numeric(precision=5, scale=2),
                nullable=False,
                server_default=sa.text("0.00"),
            ),
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            "gain_db >= -24.00 AND gain_db <= 24.00",
        )


def downgrade() -> None:
    """Clip Gain Column만 역순으로 제거한다."""

    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        for table_name, _constraint_name in reversed(TABLES):
            metadata = sa.MetaData()
            reflected = sa.Table(table_name, metadata, autoload_with=connection)
            for constraint in tuple(reflected.constraints):
                sql = str(getattr(constraint, "sqltext", ""))
                if isinstance(constraint, sa.CheckConstraint) and "gain_db" in sql:
                    reflected.constraints.remove(constraint)
            for column in reflected.columns:
                for constraint in tuple(column.constraints):
                    sql = str(getattr(constraint, "sqltext", ""))
                    if isinstance(constraint, sa.CheckConstraint) and "gain_db" in sql:
                        column.constraints.remove(constraint)
            with op.batch_alter_table(table_name, recreate="always", copy_from=reflected) as batch:
                batch.drop_column("gain_db")
        return
    for table_name, constraint_name in reversed(TABLES):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.drop_column(table_name, "gain_db")
