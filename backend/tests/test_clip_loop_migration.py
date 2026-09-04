"""Clip Loop revision 0027 deterministic backfill and constraint proofs."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend.db.session import create_database_engine
from backend.tests.test_clip_gain_migration import _config, _seed_pre_gain_rows

PREVIOUS = "20260903_0026"
REVISION = "20260905_0027"
TABLES = (
    ("composition_clips", ""),
    ("composition_snapshot_clips", ""),
    ("working_preview_render_clips", "_us"),
)


def test_clip_loop_upgrade_backfills_working_snapshot_and_preview_rows(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clip-loop.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, "20260830_0025")
    _seed_pre_gain_rows(database_url)
    command.upgrade(config, PREVIOUS)

    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        before = {
            table: connection.execute(text(f"SELECT * FROM {table}")).mappings().one()
            for table, _ in TABLES
        }
    engine.dispose()

    command.upgrade(config, REVISION)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        for table, suffix in TABLES:
            row = connection.execute(text(f"SELECT * FROM {table}")).mappings().one()
            assert row[f"timeline_duration{suffix}"] == (
                row[f"source_out{suffix}"] - row[f"source_in{suffix}"]
            )
            assert row["loop_enabled"] == 0
            assert row[f"loop_phase{suffix}"] == 0
            for key, value in before[table].items():
                assert row[key] == value
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
    engine.dispose()


def test_clip_loop_fade_constraint_uses_short_timeline_duration(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clip-loop-fade.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, "20260830_0025")
    _seed_pre_gain_rows(database_url)
    command.upgrade(config, REVISION)
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE composition_clips SET loop_enabled = 1, timeline_duration = 500000, "
                "fade_in = 200000, fade_out = 300000"
            )
        )
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE composition_clips SET fade_out = 300001"))
    engine.dispose()


def test_clip_loop_downgrade_and_reupgrade_has_no_schema_drift(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clip-loop-cycle.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, "20260830_0025")
    _seed_pre_gain_rows(database_url)
    command.upgrade(config, REVISION)
    command.downgrade(config, PREVIOUS)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        for table, suffix in TABLES:
            columns = {item["name"] for item in inspect(connection).get_columns(table)}
            assert f"timeline_duration{suffix}" not in columns
            assert "loop_enabled" not in columns
            assert f"loop_phase{suffix}" not in columns
    engine.dispose()
    command.upgrade(config, REVISION)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        for table, suffix in TABLES:
            columns = {item["name"] for item in inspect(connection).get_columns(table)}
            assert {f"timeline_duration{suffix}", "loop_enabled", f"loop_phase{suffix}"} <= columns
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
    engine.dispose()
