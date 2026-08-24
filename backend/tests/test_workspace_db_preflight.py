"""Workspace DB preflight 도구의 read-only·backup 계약 검증."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.db.workspace_preflight import (
    PREVIOUS_REVISION,
    RUNTIME_TABLES,
    TARGET_REVISION,
    WORKSPACE_TABLES,
    PreflightError,
    collect_inventory,
    create_verified_backup,
    mask_path,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_path: Path) -> Config:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def _create_runtime_fixture(database_path: Path) -> None:
    command.upgrade(_alembic_config(database_path), PREVIOUS_REVISION)


def _revision_and_tables(database_path: Path) -> tuple[str, set[str]]:
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
    engine.dispose()
    return revision, tables


def test_inventory_is_read_only_and_reports_known_drift(tmp_path: Path) -> None:
    database_path = tmp_path / "runtime-fixture.sqlite3"
    _create_runtime_fixture(database_path)
    checksum_before = sha256_file(database_path)

    with pytest.raises(PreflightError, match="confirm-read-approved"):
        collect_inventory(database_path)

    inventory = collect_inventory(database_path, read_approved=True)

    assert sha256_file(database_path) == checksum_before
    assert inventory["read_only"] is True
    assert inventory["alembic_revision"] == PREVIOUS_REVISION
    assert inventory["table_count"] == 14
    assert set(inventory["runtime_tables_present"]) == RUNTIME_TABLES
    assert inventory["workspace_tables_present"] == []
    assert inventory["integrity_check"] == ["ok"]
    assert inventory["quick_check"] == ["ok"]
    assert inventory["foreign_key_violation_count"] == 0
    assert inventory["schema_drift"]["blockers"] == []
    assert any(
        "idempotency_records post-target nullable columns absent" in item
        for item in inventory["schema_drift"]["acceptable"]
    )
    assert any(
        "pipeline_jobs.input_snapshot nullable drift" in warning
        for warning in inventory["schema_drift"]["warnings"]
    )
    assert inventory["ready_for_migration"] is False
    assert str(database_path.resolve()) not in str(inventory)


def test_backup_requires_confirmation_and_restore_preserves_runtime_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "runtime-fixture.sqlite3"
    backup_root = tmp_path / "backups"
    _create_runtime_fixture(database_path)
    source_checksum = sha256_file(database_path)

    with pytest.raises(PreflightError, match="confirm-create-backup"):
        create_verified_backup(
            database_path,
            backup_root,
            confirmed=False,
            read_approved=False,
            writers_stopped=False,
        )

    timestamp = datetime(2026, 8, 6, 12, 34, 56, tzinfo=UTC)
    backup = create_verified_backup(
        database_path,
        backup_root,
        confirmed=True,
        read_approved=True,
        writers_stopped=True,
        timestamp=timestamp,
    )
    backup_path = (
        backup_root / f"dohamusic-before-{TARGET_REVISION}-20260806-123456.sqlite3"
    )

    assert sha256_file(database_path) == source_checksum
    assert backup_path.is_file()
    assert backup["checksum_sha256"] == sha256_file(backup_path)
    assert backup["integrity_check"] == ["ok"]
    assert backup["alembic_revision"] == PREVIOUS_REVISION
    assert backup["table_count"] == 14
    assert backup["row_counts_match"] is True

    migrated_copy = tmp_path / "migration-dry-run.sqlite3"
    shutil.copy2(backup_path, migrated_copy)
    command.upgrade(_alembic_config(migrated_copy), TARGET_REVISION)
    migrated_revision, migrated_tables = _revision_and_tables(migrated_copy)
    assert migrated_revision == TARGET_REVISION
    assert migrated_tables == RUNTIME_TABLES | WORKSPACE_TABLES

    restored_copy = tmp_path / "restored-from-backup.sqlite3"
    shutil.copy2(backup_path, restored_copy)
    restored_revision, restored_tables = _revision_and_tables(restored_copy)
    assert restored_revision == PREVIOUS_REVISION
    assert restored_tables == RUNTIME_TABLES
    assert collect_inventory(restored_copy, read_approved=True)["integrity_check"] == [
        "ok"
    ]


def test_mask_path_hides_parent_directories(tmp_path: Path) -> None:
    database_path = tmp_path / "private" / "dohamusic.db"
    masked = mask_path(database_path)

    assert masked.endswith(".../dohamusic.db")
    assert "private" not in masked
    assert str(tmp_path) not in masked
