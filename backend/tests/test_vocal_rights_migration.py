"""Fixture-only additive migration, legacy preservation and audit downgrade gate."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event as sa_event
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from backend.db import vocal_rights_schema_v1
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.db.vocal_rights_schema_v1 import TABLE_NAMES, integrity_ddl
from backend.models import VoiceProfile
from backend.models.workspace import Approval, JobOutput, ModelUsage, RecordingEnrollment
from backend.models.workspace.vocal_rights import VocalRightsScopeGuard
from backend.repositories.workspace.vocal_rights_repository import VocalRightsRepository
from backend.tests.test_vocal_rights_persistence import seed_legacy

ROOT = Path(__file__).resolve().parents[2]
REVISION = "20260918_0036"
PARENT = "20260911_0035"


def config(url):
    result = Config(str(ROOT / "backend" / "alembic.ini"))
    result.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    result.set_main_option("sqlalchemy.url", url)
    return result


def snapshot(engine, tables):
    with engine.connect() as connection:
        return {
            table: connection.execute(text(f'SELECT * FROM "{table}"')).all() for table in tables
        }


def test_single_additive_revision_and_exact_parent():
    script = ScriptDirectory.from_config(config("sqlite://"))
    assert script.get_heads() == [REVISION]
    assert script.get_revision(REVISION).down_revision == PARENT
    assert len(TABLE_NAMES) == 11


def test_fresh_upgrade_empty_downgrade_reupgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'roundtrip.db').as_posix()}"
    command.upgrade(config(url), "head")
    engine = create_database_engine(url)
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
        assert connection.scalar(text("PRAGMA integrity_check")) == "ok"
        assert not connection.execute(text("PRAGMA foreign_key_check")).all()
        triggers = connection.scalars(
            text(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND (name LIKE 'vocal_rights_%' OR name LIKE 'vocal_completion_%')"
            )
        ).all()
        assert len(triggers) == len(integrity_ddl())
    command.downgrade(config(url), PARENT)
    assert set(TABLE_NAMES).isdisjoint(inspect(engine).get_table_names())
    command.upgrade(config(url), "head")
    assert set(TABLE_NAMES) <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_representative_legacy_upgrade_preserves_every_old_row_without_backfill(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    command.upgrade(config(url), PARENT)
    engine = create_database_engine(url)
    factory = create_session_factory(url)
    with factory.begin() as session:
        graph = seed_legacy(session)
        enrollment = RecordingEnrollment(
            workspace_id=graph["workspace"],
            recording_asset_version_id=graph["versions"][0],
            status="completed",
            consent_policy_version="synthetic-v1",
            consent_evidence_id="synthetic-enrollment",
            created_by=graph["owner"],
        )
        session.add(enrollment)
        session.flush()
        for purpose in ("training", "voice_conversion", "arbitrary_legacy_purpose"):
            session.add(
                Approval(
                    asset_version_id=graph["versions"][0],
                    usage_purpose=purpose,
                    status="approved",
                    approved_by=graph["owner"],
                    evidence_id="synthetic-legacy",
                    decided_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
        for consent in (True, False):
            session.add(
                VoiceProfile(
                    name="Synthetic only",
                    reference_file_path="synthetic-not-a-real-file",
                    consent_confirmed=consent,
                    consent_text_version="synthetic-v1",
                )
            )
        session.add(
            JobOutput(
                job_id=graph["job"],
                artifact_id=graph["artifact"],
                output_order=0,
                output_role="corrected_vocal",
            )
        )
        session.add(
            ModelUsage(
                job_id=graph["job"],
                asset_version_id=graph["versions"][1],
                provider_id="dohavocal",
                model_manifest_id="synthetic@1",
                model_id="synthetic",
                model_version="1",
                api_contract_version="0.2.0",
                license_status="unknown",
                commercial_usage_status="unknown",
            )
        )
    old_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    before = snapshot(engine, old_tables)
    old_schema = {
        table: [column["name"] for column in inspect(engine).get_columns(table)]
        for table in old_tables
    }
    command.upgrade(config(url), "head")
    assert snapshot(engine, old_tables) == before
    assert {
        table: [column["name"] for column in inspect(engine).get_columns(table)]
        for table in old_tables
    } == old_schema
    with engine.connect() as connection:
        assert all(
            connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0 for table in TABLE_NAMES
        )
        assert not connection.execute(text("PRAGMA foreign_key_check")).all()
    command.downgrade(config(url), PARENT)
    assert snapshot(engine, old_tables) == before
    engine.dispose()


def test_downgrade_refuses_even_empty_authority_anchor_preserving_audit(tmp_path):
    url = f"sqlite:///{(tmp_path / 'blocked.db').as_posix()}"
    command.upgrade(config(url), "head")
    factory = create_session_factory(url)
    with factory.begin() as session:
        graph = seed_legacy(session)
        guard = VocalRightsRepository(session).ensure_scope_guard(
            graph["owner"], graph["workspace"]
        )
        guard_id = guard.scope_guard_id
    with pytest.raises(RuntimeError, match="audit facts exist"):
        command.downgrade(config(url), PARENT)
    with factory.begin() as session:
        assert session.get(VocalRightsScopeGuard, guard_id) is not None
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == REVISION


def test_migration_and_metadata_constraints_match(tmp_path):
    url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    command.upgrade(config(url), "head")
    engine = create_database_engine(url)
    inspector = inspect(engine)
    for name in TABLE_NAMES:
        model = Base.metadata.tables[name]
        assert {column["name"] for column in inspector.get_columns(name)} == set(
            model.columns.keys()
        )
        assert {tuple(item["column_names"]) for item in inspector.get_unique_constraints(name)} == {
            tuple(column.name for column in constraint.columns)
            for constraint in model.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert len(inspector.get_foreign_keys(name)) == len(model.foreign_key_constraints)
        assert {item["name"] for item in inspector.get_indexes(name)} == {
            index.name for index in model.indexes
        }
    engine.dispose()


def test_upgrade_ddl_failure_rolls_back_all_new_tables_and_version(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'ddl-failure.db').as_posix()}"
    command.upgrade(config(url), PARENT)
    monkeypatch.setattr(
        vocal_rights_schema_v1,
        "integrity_ddl",
        lambda: integrity_ddl() + ("SYNTHETIC INVALID DDL",),
    )
    with pytest.raises(OperationalError):
        command.upgrade(config(url), "head")
    engine = create_database_engine(url)
    assert set(TABLE_NAMES).isdisjoint(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT
        assert not connection.execute(text("PRAGMA foreign_key_check")).all()
    engine.dispose()


def test_metadata_bootstrap_ddl_failure_is_atomic(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'metadata-failure.db').as_posix()}")

    def fail_after_create(target, connection, **kwargs):
        raise RuntimeError("synthetic metadata failure")

    sa_event.listen(Base.metadata, "after_create", fail_after_create)
    try:
        with pytest.raises(RuntimeError, match="synthetic metadata failure"):
            Base.metadata.create_all(engine)
        assert inspect(engine).get_table_names() == []
    finally:
        sa_event.remove(Base.metadata, "after_create", fail_after_create)
        engine.dispose()
