"""SQLite startup migration and foreign-key safety tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from backend.app.factory import create_app, run_startup_migration
from backend.core.config import Settings
from backend.db.migrations import upgrade_database
from backend.db.session import create_database_engine
from backend.db.sqlite import configure_sqlite_foreign_keys


def test_runtime_file_sqlite_connection_enables_foreign_keys(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}"
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    engine.dispose()


def test_runtime_in_memory_sqlite_connection_enables_foreign_keys() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    engine.dispose()


def test_runtime_sqlite_rejects_foreign_key_violation() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    metadata = MetaData()
    parent = Table("parent", metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey(parent.c.id), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(insert(child).values(id=1, parent_id=999))
    engine.dispose()


def test_non_sqlite_engine_does_not_register_pragma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listen = Mock()
    monkeypatch.setattr("backend.db.sqlite.event.listen", listen)
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    assert configure_sqlite_foreign_keys(engine) is engine  # type: ignore[arg-type]
    listen.assert_not_called()


def test_automatic_migration_defaults_to_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrade = Mock()
    monkeypatch.setattr("backend.app.factory.upgrade_database", upgrade)

    settings = Settings()
    run_startup_migration(settings)

    assert settings.auto_migrate is False
    upgrade.assert_not_called()


def test_app_startup_does_not_migrate_without_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'startup.db').as_posix()}"
    upgrade_database(database_url)
    upgrade = Mock()
    monkeypatch.setattr("backend.app.factory.upgrade_database", upgrade)
    app = create_app(
        Settings(
            database_url=database_url,
            storage_root=tmp_path / "storage",
            log_level="WARNING",
        )
    )

    with TestClient(app):
        pass

    upgrade.assert_not_called()


def test_explicit_false_does_not_run_automatic_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrade = Mock()
    monkeypatch.setattr("backend.app.factory.upgrade_database", upgrade)

    run_startup_migration(Settings(auto_migrate=False))

    upgrade.assert_not_called()


def test_explicit_opt_in_runs_existing_migration_helper_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrade = Mock()
    monkeypatch.setattr("backend.app.factory.upgrade_database", upgrade)
    settings = Settings(database_url="sqlite:///temporary-test.db", auto_migrate=True)

    run_startup_migration(settings)

    upgrade.assert_called_once_with(settings.database_url)


def test_auto_migrate_environment_setting_is_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOHAMUSIC_AUTO_MIGRATE", "true")

    assert Settings.from_environment().auto_migrate is True


def test_sqlite_helper_type_contract() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    assert isinstance(engine, Engine)
    engine.dispose()
