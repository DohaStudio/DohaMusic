from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260911_0034"
REVISION = "20260911_0035"
TABLE = "music_director_candidate_materializations"


def _config(database: Path) -> Config:
    value = Config(str(ROOT / "backend" / "alembic.ini"))
    value.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    value.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return value


def _revision(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text("select version_num from alembic_version")).scalar_one()


def test_0035_is_single_successor_head(tmp_path) -> None:
    value = _config(tmp_path / "head.db")
    script = ScriptDirectory.from_config(value)
    assert script.get_heads() == ["20260918_0037"]
    assert script.get_revision(REVISION).down_revision == PREVIOUS_REVISION


def test_0035_upgrade_empty_downgrade_and_reupgrade(tmp_path) -> None:
    database = tmp_path / "roundtrip.db"
    value = _config(database)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    command.upgrade(value, PREVIOUS_REVISION)
    command.upgrade(value, REVISION)
    assert _revision(engine) == REVISION
    assert TABLE in inspect(engine).get_table_names()
    command.downgrade(value, PREVIOUS_REVISION)
    assert _revision(engine) == PREVIOUS_REVISION
    assert TABLE not in inspect(engine).get_table_names()
    command.upgrade(value, "head")
    assert _revision(engine) == "20260918_0037"
    engine.dispose()


def test_0035_fresh_database_reaches_head(tmp_path) -> None:
    database = tmp_path / "fresh.db"
    value = _config(database)
    command.upgrade(value, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert _revision(engine) == "20260918_0037"
    columns = {column["name"] for column in inspect(engine).get_columns(TABLE)}
    assert columns == {
        "materialization_id",
        "job_id",
        "ordinal",
        "materialization_key",
        "proposal_digest",
        "planned_run_id",
        "planned_candidate_id",
        "planned_asset_id",
        "planned_asset_version_id",
        "planned_artifact_id",
        "storage_domain",
        "storage_key",
        "status",
        "version",
        "created_at",
        "updated_at",
    }
    engine.dispose()


def test_0035_downgrade_with_materialization_data_fails_closed(tmp_path) -> None:
    database = tmp_path / "data.db"
    value = _config(database)
    command.upgrade(value, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.execute(
            text(
                f"INSERT INTO {TABLE} VALUES "
                "(:id,:job,0,:key,:digest,:run,:candidate,:asset,:version,:artifact,"
                ":domain,:storage_key,'intended',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {
                "id": "00000000000000000000000000000001",
                "job": "00000000000000000000000000000002",
                "key": "a" * 64,
                "digest": "b" * 64,
                "run": "00000000000000000000000000000003",
                "candidate": "00000000000000000000000000000004",
                "asset": "00000000000000000000000000000005",
                "version": "00000000000000000000000000000006",
                "artifact": "00000000000000000000000000000007",
                "domain": "music",
                "storage_key": "runs/music-director/test.json",
            },
        )
    with pytest.raises(RuntimeError, match="materialization"):
        command.downgrade(value, PREVIOUS_REVISION)
    assert _revision(engine) == REVISION
    engine.dispose()
