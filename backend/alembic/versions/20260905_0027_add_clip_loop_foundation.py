"""Add canonical Clip timeline duration and loop geometry.

Revision ID: 20260905_0027
Revises: 20260903_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0027"
down_revision: str | Sequence[str] | None = "20260903_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    (
        "composition_clips",
        "",
        "ck_composition_clips_fade_range",
        "composition_clips",
    ),
    (
        "composition_snapshot_clips",
        "",
        "ck_composition_snapshot_clips_fade_range",
        "composition_snapshot_clips",
    ),
    (
        "working_preview_render_clips",
        "_us",
        "ck_working_preview_clip_fade_range",
        "working_preview_clip",
    ),
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _upgrade_sqlite()
        return
    for table, suffix, fade_constraint, constraint_prefix in TABLES:
        source_in = "source_in" + suffix
        source_out = "source_out" + suffix
        duration = "timeline_duration" + suffix
        phase = "loop_phase" + suffix
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(fade_constraint, type_="check")
            batch.add_column(sa.Column(duration, sa.BigInteger(), nullable=True))
            batch.add_column(
                sa.Column(
                    "loop_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
            batch.add_column(sa.Column(phase, sa.BigInteger(), nullable=False, server_default="0"))
        op.execute(sa.text(f"UPDATE {table} SET {duration} = {source_out} - {source_in}"))
        with op.batch_alter_table(table) as batch:
            batch.alter_column(duration, nullable=False)
            batch.create_check_constraint(
                f"ck_{constraint_prefix}_positive_timeline_duration",
                f"{duration} > 0",
            )
            batch.create_check_constraint(
                f"ck_{constraint_prefix}_non_negative_loop_phase",
                f"{phase} >= 0",
            )
            batch.create_check_constraint(
                f"ck_{constraint_prefix}_loop_geometry",
                (
                    f"(loop_enabled AND {phase} < {source_out} - {source_in}) OR "
                    f"(NOT loop_enabled AND {duration} = {source_out} - {source_in} "
                    f"AND {phase} = 0)"
                ),
            )
            batch.create_check_constraint(
                fade_constraint,
                f"fade_out{suffix} >= 0 AND fade_in{suffix} + fade_out{suffix} <= {duration}",
            )


def _upgrade_sqlite() -> None:
    connection = op.get_bind()
    for table, suffix, fade_constraint, constraint_prefix in TABLES:
        source_in = "source_in" + suffix
        source_out = "source_out" + suffix
        duration = "timeline_duration" + suffix
        phase = "loop_phase" + suffix
        op.add_column(table, sa.Column(duration, sa.BigInteger(), nullable=True))
        op.add_column(
            table,
            sa.Column("loop_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.add_column(table, sa.Column(phase, sa.BigInteger(), nullable=False, server_default="0"))
        op.execute(sa.text(f"UPDATE {table} SET {duration} = {source_out} - {source_in}"))
        metadata = sa.MetaData()
        reflected = sa.Table(table, metadata, autoload_with=connection)
        reflected.c[duration].nullable = False
        for constraint in tuple(reflected.constraints):
            if isinstance(constraint, sa.CheckConstraint) and "fade_out" in str(constraint.sqltext):
                reflected.constraints.remove(constraint)
        reflected.append_constraint(
            sa.CheckConstraint(
                f"fade_out{suffix} >= 0 AND fade_in{suffix} + fade_out{suffix} <= {duration}",
                name=fade_constraint,
            )
        )
        reflected.append_constraint(
            sa.CheckConstraint(
                f"{duration} > 0",
                name=f"ck_{constraint_prefix}_positive_timeline_duration",
            )
        )
        reflected.append_constraint(
            sa.CheckConstraint(
                f"{phase} >= 0",
                name=f"ck_{constraint_prefix}_non_negative_loop_phase",
            )
        )
        reflected.append_constraint(
            sa.CheckConstraint(
                (
                    f"(loop_enabled AND {phase} < {source_out} - {source_in}) OR "
                    f"(NOT loop_enabled AND {duration} = {source_out} - {source_in} "
                    f"AND {phase} = 0)"
                ),
                name=f"ck_{constraint_prefix}_loop_geometry",
            )
        )
        with op.batch_alter_table(table, recreate="always", copy_from=reflected):
            pass


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _downgrade_sqlite()
        return
    for table, suffix, fade_constraint, constraint_prefix in reversed(TABLES):
        source_in = "source_in" + suffix
        source_out = "source_out" + suffix
        duration = "timeline_duration" + suffix
        phase = "loop_phase" + suffix
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(fade_constraint, type_="check")
            batch.drop_constraint(f"ck_{constraint_prefix}_loop_geometry", type_="check")
            batch.drop_constraint(f"ck_{constraint_prefix}_non_negative_loop_phase", type_="check")
            batch.drop_constraint(
                f"ck_{constraint_prefix}_positive_timeline_duration", type_="check"
            )
            batch.create_check_constraint(
                fade_constraint,
                (
                    f"fade_out{suffix} >= 0 AND "
                    f"fade_in{suffix} + fade_out{suffix} <= {source_out} - {source_in}"
                ),
            )
            batch.drop_column(phase)
            batch.drop_column("loop_enabled")
            batch.drop_column(duration)


def _downgrade_sqlite() -> None:
    connection = op.get_bind()
    for table, suffix, fade_constraint, _constraint_prefix in reversed(TABLES):
        source_in = "source_in" + suffix
        source_out = "source_out" + suffix
        duration = "timeline_duration" + suffix
        phase = "loop_phase" + suffix
        fade_in = "fade_in" + suffix
        fade_out = "fade_out" + suffix
        metadata = sa.MetaData()
        reflected = sa.Table(table, metadata, autoload_with=connection)
        for constraint in tuple(reflected.constraints):
            sql = str(getattr(constraint, "sqltext", ""))
            if isinstance(constraint, sa.CheckConstraint) and any(
                token in sql for token in ("loop_", "timeline_duration", "fade_out")
            ):
                reflected.constraints.remove(constraint)
        reflected.c[fade_out].constraints.add(
            sa.CheckConstraint(
                f"{fade_out} >= 0 AND {fade_in} + {fade_out} <= {source_out} - {source_in}",
                name=fade_constraint,
            )
        )
        with op.batch_alter_table(table, recreate="always", copy_from=reflected) as batch:
            batch.drop_column(phase)
            batch.drop_column("loop_enabled")
            batch.drop_column(duration)
