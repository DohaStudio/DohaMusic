from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260908_0032"
REVISION = "20260911_0033"
CURRENT_HEAD = "20260918_0036"
TABLES = {"music_director_runs", "music_director_candidates"}


def config(database: Path) -> Config:
    value = Config(str(ROOT / "backend" / "alembic.ini"))
    value.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    value.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return value


def revision(engine) -> str:
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_0033_is_single_successor_head(tmp_path):
    value = config(tmp_path / "head.db")
    script = ScriptDirectory.from_config(value)
    assert script.get_heads() == [CURRENT_HEAD]
    assert script.get_revision(REVISION).down_revision == PREVIOUS_REVISION


def test_0033_upgrade_downgrade_reupgrade(tmp_path):
    database = tmp_path / "roundtrip.db"
    value = config(database)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    command.upgrade(value, PREVIOUS_REVISION)
    before = set(inspect(engine).get_table_names())
    command.upgrade(value, REVISION)
    assert revision(engine) == REVISION
    assert set(inspect(engine).get_table_names()) >= TABLES
    command.downgrade(value, PREVIOUS_REVISION)
    assert revision(engine) == PREVIOUS_REVISION
    assert set(inspect(engine).get_table_names()) == before
    command.upgrade(value, "head")
    assert revision(engine) == CURRENT_HEAD
    assert set(inspect(engine).get_table_names()) >= TABLES
    engine.dispose()


def test_fresh_database_reaches_0033_with_foreign_keys(tmp_path):
    database = tmp_path / "fresh.db"
    value = config(database)
    command.upgrade(value, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert revision(engine) == CURRENT_HEAD
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) >= TABLES
    run_fks = {fk["name"] for fk in inspector.get_foreign_keys("music_director_runs")}
    assert {
        "fk_music_director_runs_project_snapshot",
        "fk_music_director_runs_selected_candidate",
        "fk_music_director_runs_applied_candidate",
    } <= run_fks
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()


def test_0033_preserves_preexisting_rows_and_drops_only_d5_data(tmp_path):
    database = tmp_path / "data-roundtrip.db"
    value = config(database)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    command.upgrade(value, PREVIOUS_REVISION)
    workspace_id = "11111111111111111111111111111111"
    owner_id = "22222222222222222222222222222222"
    project_id = "33333333333333333333333333333333"
    snapshot_id = "44444444444444444444444444444444"
    job_id = "55555555555555555555555555555555"
    asset_id = "66666666666666666666666666666666"
    version_id = "77777777777777777777777777777777"
    artifact_id = "88888888888888888888888888888888"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workspaces "
                "(workspace_id, owner_id, name, lifecycle_status, created_at, "
                "updated_at, deleted_at) "
                "VALUES (:workspace_id, :owner_id, 'preserved', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, NULL)"
            ),
            {"workspace_id": workspace_id, "owner_id": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO music_projects "
                "(project_id, workspace_id, title, lifecycle_status, created_by, "
                "created_at, updated_at, deleted_at) VALUES (:project, :workspace, "
                "'project', 'active', :owner, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)"
            ),
            {"project": project_id, "workspace": workspace_id, "owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO composition_snapshots "
                "(composition_snapshot_id, project_id, snapshot_version, "
                "mix_settings_snapshot, master_gain_db, provider_versions, "
                "model_manifest_ids, created_by, created_at) VALUES "
                "(:snapshot, :project, 1, '{}', 0, '{}', '{}', :owner, CURRENT_TIMESTAMP)"
            ),
            {"snapshot": snapshot_id, "project": project_id, "owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO jobs (job_id, project_id, workspace_id, "
                "composition_snapshot_id, job_type, status, api_contract_version, "
                "settings_snapshot, requested_by, attempt, created_at) VALUES "
                "(:job, :project, :workspace, :snapshot, 'music_director', 'running', "
                "'1', '{}', :owner, 1, CURRENT_TIMESTAMP)"
            ),
            {
                "job": job_id,
                "project": project_id,
                "workspace": workspace_id,
                "snapshot": snapshot_id,
                "owner": owner_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO assets (asset_id, workspace_id, owner_id, asset_type, "
                "lifecycle_status, created_at, updated_at, deleted_at) VALUES "
                "(:asset, :workspace, :owner, 'candidate', 'active', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, NULL)"
            ),
            {"asset": asset_id, "workspace": workspace_id, "owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO asset_versions (asset_version_id, asset_id, version_number, "
                "version_origin, settings_snapshot, created_by, created_at) VALUES "
                "(:version, :asset, 1, 'music_director', '{}', :owner, CURRENT_TIMESTAMP)"
            ),
            {"version": version_id, "asset": asset_id, "owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO artifacts (artifact_id, asset_version_id, artifact_kind, "
                "media_type, size_bytes, checksum_algorithm, artifact_checksum, "
                "producer_type, retention_status, created_at) VALUES "
                "(:artifact, :version, 'music_director_proposal', 'application/json', "
                "10, 'sha256', :digest, 'music_director', 'active', CURRENT_TIMESTAMP)"
            ),
            {"artifact": artifact_id, "version": version_id, "digest": "a" * 64},
        )
    command.upgrade(value, REVISION)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO music_director_runs "
                "(run_id, job_id, project_id, composition_snapshot_id, version, "
                "created_at, updated_at) "
                "VALUES (:run, :job, :project, :snapshot, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "run": "99999999999999999999999999999999",
                "job": job_id,
                "project": project_id,
                "snapshot": snapshot_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO music_director_candidates "
                "(candidate_id, run_id, ordinal, status, proposal_digest, "
                "candidate_asset_version_id, proposal_artifact_id, created_at) "
                "VALUES (:candidate, :run, 0, 'generated', :digest, :version, "
                ":artifact, CURRENT_TIMESTAMP)"
            ),
            {
                "candidate": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "run": "99999999999999999999999999999999",
                "digest": "a" * 64,
                "version": version_id,
                "artifact": artifact_id,
            },
        )
    engine.dispose()
    command.downgrade(value, PREVIOUS_REVISION)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert not TABLES.intersection(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT name FROM workspaces WHERE workspace_id = :workspace_id"),
                {"workspace_id": workspace_id},
            )
            == "preserved"
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()
