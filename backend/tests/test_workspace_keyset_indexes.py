"""Workspace·MusicProject keyset 복합 Index와 Query Plan 검증."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import backend.models  # noqa: F401
from backend.db.base import Base
from backend.db.session import create_database_engine

ROOT = Path(__file__).resolve().parents[2]
REVISION = "20260807_0013"
PREVIOUS_REVISION = "20260806_0012"
KEYSET_INDEXES = {
    "ix_workspaces_active_keyset": (
        "workspaces",
        ("deleted_at", "created_at", "workspace_id"),
    ),
    "ix_workspaces_owner_active_keyset": (
        "workspaces",
        ("owner_id", "deleted_at", "created_at", "workspace_id"),
    ),
    "ix_music_projects_workspace_active_keyset": (
        "music_projects",
        ("workspace_id", "deleted_at", "created_at", "project_id"),
    ),
}


def _config(database_url: str) -> Config:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _workspace_id(value: int) -> str:
    return f"{value:032x}"


def _project_id(value: int) -> str:
    return f"{0x10000000000000000000000000000000 + value:032x}"


def _insert_fixtures(database_url: str) -> None:
    engine = create_database_engine(database_url)
    origin = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    workspace_rows = []
    for identifier in range(1, 721):
        created_at = origin - timedelta(hours=identifier // 12)
        workspace_rows.append(
            {
                "workspace_id": _workspace_id(identifier),
                "owner_id": _workspace_id(10_000 + identifier % 8),
                "name": f"Workspace {identifier}",
                "lifecycle_status": "active",
                "updated_at": created_at,
                "created_at": created_at,
                "deleted_at": (created_at + timedelta(days=1) if identifier % 7 == 0 else None),
            }
        )
    project_rows = []
    for identifier in range(1, 1_201):
        created_at = origin - timedelta(hours=identifier // 15)
        project_rows.append(
            {
                "project_id": _project_id(identifier),
                "workspace_id": _workspace_id(identifier % 12 + 1),
                "title": f"Project {identifier}",
                "description": None,
                "lifecycle_status": "active",
                "created_by": _workspace_id(20_000 + identifier),
                "updated_at": created_at,
                "created_at": created_at,
                "deleted_at": (created_at + timedelta(days=1) if identifier % 9 == 0 else None),
            }
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspaces "
                "(workspace_id, owner_id, name, lifecycle_status, updated_at, "
                "created_at, deleted_at) VALUES "
                "(:workspace_id, :owner_id, :name, :lifecycle_status, :updated_at, "
                ":created_at, :deleted_at)"
            ),
            workspace_rows,
        )
        connection.execute(
            text(
                "INSERT INTO music_projects "
                "(project_id, workspace_id, title, description, lifecycle_status, "
                "created_by, updated_at, created_at, deleted_at) VALUES "
                "(:project_id, :workspace_id, :title, :description, "
                ":lifecycle_status, :created_by, :updated_at, :created_at, "
                ":deleted_at)"
            ),
            project_rows,
        )
        connection.exec_driver_sql("ANALYZE")
    engine.dispose()


def _queries() -> dict[str, tuple[str, tuple[object, ...], str]]:
    anchor_time = "2026-08-06 12:00:00.000000"
    workspace_columns = (
        "workspace_id, owner_id, name, lifecycle_status, updated_at, created_at, deleted_at"
    )
    project_columns = (
        "project_id, workspace_id, title, description, lifecycle_status, "
        "created_by, updated_at, created_at, deleted_at"
    )
    return {
        "workspace_all_first": (
            (
                f"SELECT {workspace_columns} FROM workspaces "
                "WHERE deleted_at IS NULL "
                "ORDER BY created_at DESC, workspace_id DESC LIMIT 25"
            ),
            (),
            "ix_workspaces_active_keyset",
        ),
        "workspace_all_after": (
            (
                f"SELECT {workspace_columns} FROM workspaces "
                "WHERE deleted_at IS NULL AND "
                "(created_at < ? OR (created_at = ? AND workspace_id < ?)) "
                "ORDER BY created_at DESC, workspace_id DESC LIMIT 25"
            ),
            (anchor_time, anchor_time, _workspace_id(300)),
            "ix_workspaces_active_keyset",
        ),
        "workspace_owner_first": (
            (
                f"SELECT {workspace_columns} FROM workspaces "
                "WHERE deleted_at IS NULL AND owner_id = ? "
                "ORDER BY created_at DESC, workspace_id DESC LIMIT 25"
            ),
            (_workspace_id(10_003),),
            "ix_workspaces_owner_active_keyset",
        ),
        "workspace_owner_after": (
            (
                f"SELECT {workspace_columns} FROM workspaces "
                "WHERE deleted_at IS NULL AND owner_id = ? AND "
                "(created_at < ? OR (created_at = ? AND workspace_id < ?)) "
                "ORDER BY created_at DESC, workspace_id DESC LIMIT 25"
            ),
            (_workspace_id(10_003), anchor_time, anchor_time, _workspace_id(300)),
            "ix_workspaces_owner_active_keyset",
        ),
        "project_first": (
            (
                f"SELECT {project_columns} FROM music_projects "
                "WHERE workspace_id = ? AND deleted_at IS NULL "
                "ORDER BY created_at DESC, project_id DESC LIMIT 25"
            ),
            (_workspace_id(3),),
            "ix_music_projects_workspace_active_keyset",
        ),
        "project_after": (
            (
                f"SELECT {project_columns} FROM music_projects "
                "WHERE workspace_id = ? AND deleted_at IS NULL AND "
                "(created_at < ? OR (created_at = ? AND project_id < ?)) "
                "ORDER BY created_at DESC, project_id DESC LIMIT 25"
            ),
            (_workspace_id(3), anchor_time, anchor_time, _project_id(600)),
            "ix_music_projects_workspace_active_keyset",
        ),
    }


def _plans_and_rows(database_url: str):
    engine = create_database_engine(database_url)
    plans: dict[str, str] = {}
    rows: dict[str, list[tuple[object, ...]]] = {}
    with engine.connect() as connection:
        for name, (query, parameters, _) in _queries().items():
            plans[name] = " | ".join(
                row[3]
                for row in connection.exec_driver_sql(f"EXPLAIN QUERY PLAN {query}", parameters)
            )
            rows[name] = list(connection.exec_driver_sql(query, parameters))
    engine.dispose()
    return plans, rows


def test_keyset_index_metadata_matches_contract() -> None:
    actual = {}
    for table_name in ("workspaces", "music_projects"):
        for index in Base.metadata.tables[table_name].indexes:
            if index.name in KEYSET_INDEXES:
                actual[index.name] = (
                    table_name,
                    tuple(expression.name for expression in index.expressions),
                )

    assert actual == KEYSET_INDEXES
    assert len(actual) == len(set(actual)) == 3


def test_keyset_revision_query_plans_and_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "workspace-keyset-indexes.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _config(database_url)
    script = ScriptDirectory.from_config(config)

    assert script.get_revision(REVISION).down_revision == PREVIOUS_REVISION

    command.upgrade(config, PREVIOUS_REVISION)
    _insert_fixtures(database_url)
    baseline_plans, baseline_rows = _plans_and_rows(database_url)
    assert all("USE TEMP B-TREE FOR ORDER BY" in plan for plan in baseline_plans.values())

    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        baseline_indexes = {
            index["name"]
            for table_name in ("workspaces", "music_projects")
            for index in inspect(connection).get_indexes(table_name)
        }
        baseline_counts = {
            table_name: connection.exec_driver_sql(
                f"SELECT count(*) FROM {table_name}"
            ).scalar_one()
            for table_name in ("workspaces", "music_projects")
        }
    engine.dispose()

    command.upgrade(config, REVISION)
    upgraded_plans, upgraded_rows = _plans_and_rows(database_url)
    for name, plan in upgraded_plans.items():
        expected_index = _queries()[name][2]
        assert expected_index in plan
        assert "USE TEMP B-TREE FOR ORDER BY" not in plan
        assert "SCAN workspaces" not in plan
        assert "SCAN music_projects" not in plan
        assert upgraded_rows[name] == baseline_rows[name]
        if name.startswith("workspace"):
            sort_keys = [(row[5], row[0]) for row in upgraded_rows[name]]
        else:
            sort_keys = [(row[7], row[0]) for row in upgraded_rows[name]]
        identifiers = [row[0] for row in upgraded_rows[name]]
        assert sort_keys == sorted(sort_keys, reverse=True)
        assert len(identifiers) == len(set(identifiers))

    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        inspector = inspect(connection)
        upgraded_indexes = {
            index["name"]: (
                table_name,
                tuple(index["column_names"]),
            )
            for table_name in ("workspaces", "music_projects")
            for index in inspector.get_indexes(table_name)
            if index["name"] in KEYSET_INDEXES
        }
        assert upgraded_indexes == KEYSET_INDEXES
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == REVISION
        )
    engine.dispose()

    command.downgrade(config, PREVIOUS_REVISION)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        inspector = inspect(connection)
        downgraded_indexes = {
            index["name"]
            for table_name in ("workspaces", "music_projects")
            for index in inspector.get_indexes(table_name)
        }
        downgraded_counts = {
            table_name: connection.exec_driver_sql(
                f"SELECT count(*) FROM {table_name}"
            ).scalar_one()
            for table_name in ("workspaces", "music_projects")
        }
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == PREVIOUS_REVISION
        )
        assert connection.exec_driver_sql("PRAGMA quick_check").scalar_one() == "ok"
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()

    assert not KEYSET_INDEXES.keys() & downgraded_indexes
    assert downgraded_indexes == baseline_indexes
    assert downgraded_counts == baseline_counts
