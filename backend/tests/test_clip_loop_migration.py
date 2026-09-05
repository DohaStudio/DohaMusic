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


def _table_sql(connection, table: str) -> str:
    return connection.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table},
    ).scalar_one()


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


def test_working_preview_loop_fade_constraints_downgrade_portably(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clip-loop-portable.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, "20260830_0025")
    _seed_pre_gain_rows(database_url)
    command.upgrade(config, PREVIOUS)
    command.upgrade(config, REVISION)

    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        row_0027 = (
            connection.execute(text("SELECT * FROM working_preview_render_clips")).mappings().one()
        )
        sql_0027 = _table_sql(connection, "working_preview_render_clips")
        assert {
            "fade_in_us",
            "fade_out_us",
            "timeline_duration_us",
            "loop_enabled",
            "loop_phase_us",
        } <= set(row_0027)
        assert "fade_in_us + fade_out_us <= timeline_duration_us" in sql_0027
    engine.dispose()

    command.downgrade(config, PREVIOUS)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        row_0026 = (
            connection.execute(text("SELECT * FROM working_preview_render_clips")).mappings().one()
        )
        sql_0026 = _table_sql(connection, "working_preview_render_clips")
        assert {"fade_in_us", "fade_out_us"} <= set(row_0026)
        assert {
            "timeline_duration_us",
            "loop_enabled",
            "loop_phase_us",
        }.isdisjoint(row_0026)
        assert "fade_in_us + fade_out_us <= source_out_us - source_in_us" in sql_0026
        for key in row_0026:
            assert row_0026[key] == row_0027[key]
    engine.dispose()

    command.downgrade(config, "20260830_0025")
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        row_0025 = (
            connection.execute(text("SELECT * FROM working_preview_render_clips")).mappings().one()
        )
        sql_0025 = _table_sql(connection, "working_preview_render_clips")
        assert {
            "fade_in_us",
            "fade_out_us",
            "timeline_duration_us",
            "loop_enabled",
            "loop_phase_us",
        }.isdisjoint(row_0025)
        assert all(
            token not in sql_0025
            for token in (
                "fade_in_us",
                "fade_out_us",
                "timeline_duration_us",
                "loop_enabled",
                "loop_phase_us",
            )
        )
        for key in row_0025:
            assert row_0025[key] == row_0027[key]
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
    engine.dispose()

    command.upgrade(config, PREVIOUS)
    command.upgrade(config, REVISION)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        row_reupgraded = (
            connection.execute(text("SELECT * FROM working_preview_render_clips")).mappings().one()
        )
        assert row_reupgraded == row_0027
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
    engine.dispose()


def test_clip_gain_constraint_downgrade_has_no_dangling_reference(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'clip-gain-portable.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, REVISION)
    command.downgrade(config, "20260828_0024")
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        for table, _suffix in TABLES:
            columns = {item["name"] for item in inspect(connection).get_columns(table)}
            assert "gain_db" not in columns
            assert "gain_db" not in _table_sql(connection, table)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
    engine.dispose()
