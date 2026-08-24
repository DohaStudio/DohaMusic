"""D1-A Project Composition selection migration 계약 검증."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend.db.session import create_database_engine

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260810_0017"
REVISION = "20260820_0018"


def _config(database_url: str) -> Config:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _seed_project_and_snapshot(connection, suffix: str) -> tuple[str, str]:
    owner_id = uuid4().hex
    workspace_id = uuid4().hex
    project_id = uuid4().hex
    snapshot_id = uuid4().hex
    now = datetime.now(UTC)
    connection.execute(
        text(
            "INSERT INTO workspaces "
            "(workspace_id, owner_id, name, lifecycle_status, updated_at, created_at, deleted_at) "
            "VALUES (:workspace_id, :owner_id, :name, 'active', :now, :now, NULL)"
        ),
        {
            "workspace_id": workspace_id,
            "owner_id": owner_id,
            "name": f"D1-A Workspace {suffix}",
            "now": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO music_projects "
            "(project_id, workspace_id, title, description, lifecycle_status, "
            "created_by, updated_at, created_at, deleted_at) "
            "VALUES (:project_id, :workspace_id, :title, NULL, 'active', "
            ":owner_id, :now, :now, NULL)"
        ),
        {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "title": f"D1-A Project {suffix}",
            "owner_id": owner_id,
            "now": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO composition_snapshots "
            "(composition_snapshot_id, project_id, snapshot_version, processing_chain_id, "
            "mix_settings_snapshot, provider_versions, model_manifest_ids, created_by, created_at) "
            "VALUES (:snapshot_id, :project_id, 1, NULL, '{}', '{}', '{}', :owner_id, :now)"
        ),
        {
            "snapshot_id": snapshot_id,
            "project_id": project_id,
            "owner_id": owner_id,
            "now": now,
        },
    )
    return project_id, snapshot_id


def test_selection_migration_is_nullable_safe_and_enforces_same_project(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'selection-migration.db').as_posix()}"
    config = _config(database_url)
    command.upgrade(config, PREVIOUS_REVISION)
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        first_project, first_snapshot = _seed_project_and_snapshot(connection, "A")
        _, second_snapshot = _seed_project_and_snapshot(connection, "B")

    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "project_composition_selections" in inspector.get_table_names()
        assert (
            connection.execute(
                text("SELECT count(*) FROM project_composition_selections")
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == REVISION
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        indexes = {item["name"]: item for item in inspector.get_indexes("composition_snapshots")}
        assert indexes["uq_composition_snapshots_project_identity"]["unique"] == 1
        artifact_indexes = {item["name"]: item for item in inspector.get_indexes("artifacts")}
        assert artifact_indexes["ix_artifacts_version_created"]["column_names"] == [
            "asset_version_id",
            "created_at",
            "artifact_id",
        ]
        foreign_keys = inspector.get_foreign_keys("project_composition_selections")
        assert any(
            key["constrained_columns"] == ["project_id", "selected_composition_snapshot_id"]
            and key["referred_columns"] == ["project_id", "composition_snapshot_id"]
            for key in foreign_keys
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO project_composition_selections "
                "(project_id, selected_composition_snapshot_id, updated_at, created_at) "
                "VALUES (:project_id, :snapshot_id, :now, :now)"
            ),
            {
                "project_id": first_project,
                "snapshot_id": second_snapshot,
                "now": datetime.now(UTC),
            },
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO project_composition_selections "
                "(project_id, selected_composition_snapshot_id, updated_at, created_at) "
                "VALUES (:project_id, :snapshot_id, :now, :now)"
            ),
            {
                "project_id": first_project,
                "snapshot_id": first_snapshot,
                "now": datetime.now(UTC),
            },
        )
    command.downgrade(config, PREVIOUS_REVISION)
    with engine.connect() as connection:
        assert "project_composition_selections" not in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT count(*) FROM music_projects")).scalar_one() == 2
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == PREVIOUS_REVISION
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert "ix_artifacts_version_created" not in {
            item["name"] for item in inspect(connection).get_indexes("artifacts")
        }
    engine.dispose()
