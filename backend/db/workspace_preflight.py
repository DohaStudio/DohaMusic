"""Workspace additive migration 전용 SQLite 사전 점검 도구.

이 모듈은 사용자 DB에 schema 또는 data 변경 SQL을 실행하지 않는다. Inventory는
SQLite read-only URI를 사용하고, backup은 명시적 확인 인수가 있을 때만 새 파일을
생성한다. Alembic upgrade와 downgrade 기능은 의도적으로 제공하지 않는다.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.dialects import sqlite

import backend.models  # noqa: F401
from backend.db.base import Base

PREVIOUS_REVISION = "20260801_0011"
TARGET_REVISION = "20260806_0012"
RUNTIME_TABLES = {
    "generated_files",
    "generation_jobs",
    "idempotency_records",
    "lyrics_documents",
    "pipeline_files",
    "pipeline_jobs",
    "projects",
    "stem_files",
    "stem_jobs",
    "voice_conversion_files",
    "voice_conversion_jobs",
    "voice_enrollments",
    "voice_profiles",
    "voice_samples",
}
WORKSPACE_TABLES = {
    "approvals",
    "artifacts",
    "asset_relations",
    "asset_versions",
    "assets",
    "comments",
    "composition_snapshots",
    "favorites",
    "history",
    "job_inputs",
    "job_outputs",
    "jobs",
    "model_usages",
    "music_projects",
    "processing_chains",
    "processing_steps",
    "project_assets",
    "recording_enrollments",
    "snapshot_items",
    "tags",
    "workspaces",
}
MINIMUM_FREE_BYTES = 100 * 1024 * 1024
POST_TARGET_NULLABLE_COLUMNS = {
    "idempotency_records": {
        "completed_revision",
        "result_payload",
        "result_type",
        "result_version",
    },
}


class PreflightError(RuntimeError):
    """민감한 원본 경로를 포함하지 않는 사전 점검 오류."""


def mask_path(path: Path) -> str:
    """로그와 JSON에서 절대 경로의 중간 component를 숨긴다."""

    resolved = path.expanduser().resolve(strict=False)
    anchor = resolved.anchor.replace("\\", "/")
    return f"{anchor}.../{resolved.name}"


def sha256_file(path: Path) -> str:
    """파일을 변경하지 않고 SHA-256 checksum을 계산한다."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only_connection(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise PreflightError(f"DB 파일을 찾을 수 없습니다: {mask_path(database_path)}")
    uri = f"{database_path.expanduser().resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _pragma_scalar(connection: sqlite3.Connection, pragma: str) -> Any:
    row = connection.execute(f"PRAGMA {pragma}").fetchone()
    return None if row is None else row[0]


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _row_counts(
    connection: sqlite3.Connection, table_names: set[str]
) -> dict[str, int]:
    return {
        table_name: int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}"
            ).fetchone()[0]
        )
        for table_name in sorted(table_names)
    }


def _actual_columns(
    connection: sqlite3.Connection, table_name: str
) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        f"PRAGMA table_info({_quote_identifier(table_name)})"
    ).fetchall()
    return {
        str(row["name"]): {
            "type": str(row["type"]).upper(),
            "nullable": not bool(row["notnull"] or row["pk"]),
            "primary_key": bool(row["pk"]),
        }
        for row in rows
    }


def _expected_columns(table_name: str) -> dict[str, dict[str, object]]:
    table = Base.metadata.tables[table_name]
    dialect = sqlite.dialect()
    return {
        column.name: {
            "type": str(column.type.compile(dialect=dialect)).upper(),
            "nullable": bool(column.nullable and not column.primary_key),
            "primary_key": bool(column.primary_key),
        }
        for column in table.columns
    }


def _actual_foreign_keys(
    connection: sqlite3.Connection, table_name: str
) -> set[tuple[tuple[str, ...], str, tuple[str, ...], str]]:
    grouped: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in connection.execute(
        f"PRAGMA foreign_key_list({_quote_identifier(table_name)})"
    ).fetchall():
        grouped[int(row["id"])].append(row)
    return {
        (
            tuple(
                str(row["from"]) for row in sorted(rows, key=lambda item: item["seq"])
            ),
            str(rows[0]["table"]),
            tuple(str(row["to"]) for row in sorted(rows, key=lambda item: item["seq"])),
            str(rows[0]["on_delete"]).upper(),
        )
        for rows in grouped.values()
    }


def _expected_foreign_keys(
    table_name: str,
) -> set[tuple[tuple[str, ...], str, tuple[str, ...], str]]:
    constraints = Base.metadata.tables[table_name].foreign_key_constraints
    return {
        (
            tuple(element.parent.name for element in constraint.elements),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
            str(constraint.ondelete or "NO ACTION").upper(),
        )
        for constraint in constraints
    }


def _actual_index_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(
        f"PRAGMA index_list({_quote_identifier(table_name)})"
    ).fetchall()
    return {str(row["name"]) for row in rows if str(row["origin"]).lower() == "c"}


def _expected_index_names(table_name: str) -> set[str]:
    return {
        str(index.name)
        for index in Base.metadata.tables[table_name].indexes
        if index.name
    }


def inspect_schema_drift(
    connection: sqlite3.Connection, table_names: set[str]
) -> dict[str, list[str]]:
    """현행 14개 Runtime schema와 ORM metadata 차이를 자동 수정 없이 분류한다."""

    blockers: list[str] = []
    warnings: list[str] = []
    acceptable: list[str] = []
    missing_tables = sorted(RUNTIME_TABLES - table_names)
    unexpected_tables = sorted(
        table_names - RUNTIME_TABLES - WORKSPACE_TABLES - {"alembic_version"}
    )
    if missing_tables:
        blockers.append(f"Runtime Table 누락: {', '.join(missing_tables)}")
    if unexpected_tables:
        warnings.append(f"예상 외 Table 존재: {', '.join(unexpected_tables)}")

    for table_name in sorted(RUNTIME_TABLES & table_names):
        actual_columns = _actual_columns(connection, table_name)
        expected_columns = _expected_columns(table_name)
        missing_columns = sorted(set(expected_columns) - set(actual_columns))
        allowed_missing_columns = POST_TARGET_NULLABLE_COLUMNS.get(table_name, set())
        post_target_missing_columns = sorted(
            set(missing_columns) & allowed_missing_columns
        )
        missing_columns = sorted(set(missing_columns) - allowed_missing_columns)
        extra_columns = sorted(set(actual_columns) - set(expected_columns))
        if missing_columns:
            blockers.append(f"{table_name} Column 누락: {', '.join(missing_columns)}")
        if post_target_missing_columns:
            acceptable.append(
                f"{table_name} post-target nullable columns absent: "
                f"{', '.join(post_target_missing_columns)}"
            )
        if extra_columns:
            warnings.append(f"{table_name} 예상 외 Column: {', '.join(extra_columns)}")
        for column_name in sorted(set(actual_columns) & set(expected_columns)):
            actual = actual_columns[column_name]
            expected = expected_columns[column_name]
            if actual["nullable"] != expected["nullable"]:
                message = (
                    f"{table_name}.{column_name} nullable drift: "
                    f"DB={actual['nullable']}, metadata={expected['nullable']}"
                )
                if (table_name, column_name) == ("pipeline_jobs", "input_snapshot"):
                    warnings.append(message)
                else:
                    blockers.append(message)
            if actual["type"] != expected["type"]:
                warnings.append(
                    f"{table_name}.{column_name} type 표기 차이: "
                    f"DB={actual['type']}, metadata={expected['type']}"
                )

        actual_foreign_keys = _actual_foreign_keys(connection, table_name)
        expected_foreign_keys = _expected_foreign_keys(table_name)
        if actual_foreign_keys != expected_foreign_keys:
            blockers.append(f"{table_name} FK 정의 불일치")

        actual_indexes = _actual_index_names(connection, table_name)
        expected_indexes = _expected_index_names(table_name)
        missing_indexes = sorted(expected_indexes - actual_indexes)
        extra_indexes = sorted(actual_indexes - expected_indexes)
        if missing_indexes:
            blockers.append(f"{table_name} Index 누락: {', '.join(missing_indexes)}")
        if extra_indexes:
            warnings.append(f"{table_name} 예상 외 Index: {', '.join(extra_indexes)}")

    if not blockers:
        acceptable.append("자동 검사 범위의 Runtime schema BLOCKER 없음")
    acceptable.append("SQLite 내부 autoindex는 명시적 Index 비교에서 제외")
    return {
        "blockers": blockers,
        "warnings": warnings,
        "acceptable": acceptable,
    }


def collect_inventory(
    database_path: Path, *, read_approved: bool = False
) -> dict[str, object]:
    """명시적 SQLite 파일을 read-only로 열어 data 내용 없이 상태를 집계한다."""

    if not read_approved:
        raise PreflightError("Inventory에는 --confirm-read-approved가 필요합니다.")
    resolved = database_path.expanduser().resolve()
    with _read_only_connection(resolved) as connection:
        table_names = _table_names(connection)
        alembic_revision = None
        if "alembic_version" in table_names:
            row = connection.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
            alembic_revision = None if row is None else str(row[0])
        integrity_results = [
            str(row[0]) for row in connection.execute("PRAGMA integrity_check")
        ]
        quick_results = [
            str(row[0]) for row in connection.execute("PRAGMA quick_check")
        ]
        foreign_key_violations = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        drift = inspect_schema_drift(connection, table_names)
        pragmas = {
            "application_id": int(_pragma_scalar(connection, "application_id") or 0),
            "user_version": int(_pragma_scalar(connection, "user_version") or 0),
            "journal_mode": str(_pragma_scalar(connection, "journal_mode") or ""),
            "foreign_keys": int(_pragma_scalar(connection, "foreign_keys") or 0),
            "synchronous": int(_pragma_scalar(connection, "synchronous") or 0),
            "busy_timeout_ms": int(_pragma_scalar(connection, "busy_timeout") or 0),
        }
        row_counts = _row_counts(connection, table_names - {"alembic_version"})

    file_size = resolved.stat().st_size
    required_free_bytes = max(file_size * 3, MINIMUM_FREE_BYTES)
    free_bytes = shutil.disk_usage(resolved.parent).free
    facts = {
        "integrity_check_ok": integrity_results == ["ok"],
        "quick_check_ok": quick_results == ["ok"],
        "foreign_key_violations_zero": foreign_key_violations == 0,
        "revision_is_previous_head": alembic_revision == PREVIOUS_REVISION,
        "runtime_tables_complete": RUNTIME_TABLES.issubset(table_names),
        "workspace_tables_absent": not bool(WORKSPACE_TABLES & table_names),
        "schema_drift_blockers_zero": not drift["blockers"],
        "database_file_writable_advisory": os.access(resolved, os.W_OK),
        "disk_space_advisory_ok": free_bytes >= required_free_bytes,
    }
    return {
        "database": mask_path(resolved),
        "read_only": True,
        "sqlite_version": sqlite3.sqlite_version,
        "file_size_bytes": file_size,
        "checksum_sha256": sha256_file(resolved),
        "wal_exists": Path(f"{resolved}-wal").exists(),
        "shm_exists": Path(f"{resolved}-shm").exists(),
        "alembic_revision": alembic_revision,
        "table_count": len(table_names - {"alembic_version"}),
        "runtime_tables_present": sorted(RUNTIME_TABLES & table_names),
        "workspace_tables_present": sorted(WORKSPACE_TABLES & table_names),
        "row_counts": row_counts,
        "foreign_key_violation_count": foreign_key_violations,
        "integrity_check": integrity_results,
        "quick_check": quick_results,
        "pragmas": pragmas,
        "schema_drift": drift,
        "database_facts": facts,
        "required_operator_gates": [
            "앱과 Worker 완전 종료 또는 쓰기 차단",
            "검증된 timestamp backup과 checksum 확보",
            "Alembic 연결에서 PRAGMA foreign_keys=ON 확인",
            "사용자 명시적 적용 승인",
        ],
        "ready_for_migration": False,
    }


def planned_backup_path(
    database_path: Path, backup_root: Path, *, timestamp: datetime | None = None
) -> Path:
    moment = timestamp or datetime.now(UTC)
    suffix = moment.strftime("%Y%m%d-%H%M%S")
    return backup_root / f"dohamusic-before-{TARGET_REVISION}-{suffix}.sqlite3"


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise PreflightError("backup root의 사용 가능한 상위 경로가 없습니다.")
        candidate = parent
    return candidate


def create_verified_backup(
    database_path: Path,
    backup_root: Path,
    *,
    confirmed: bool,
    read_approved: bool,
    writers_stopped: bool,
    timestamp: datetime | None = None,
) -> dict[str, object]:
    """명시적 확인 뒤 SQLite backup API로 새 backup을 만들고 검증한다."""

    if not confirmed:
        raise PreflightError("backup 생성에는 --confirm-create-backup이 필요합니다.")
    if not read_approved:
        raise PreflightError("backup에는 --confirm-read-approved가 필요합니다.")
    if not writers_stopped:
        raise PreflightError("backup에는 --confirm-writers-stopped가 필요합니다.")
    source_path = database_path.expanduser().resolve()
    source_inventory = collect_inventory(source_path, read_approved=True)
    destination = planned_backup_path(source_path, backup_root, timestamp=timestamp)
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise PreflightError(f"backup 대상이 이미 존재합니다: {mask_path(destination)}")
    required_free_bytes = max(
        int(source_inventory["file_size_bytes"]) * 3, MINIMUM_FREE_BYTES
    )
    free_bytes = shutil.disk_usage(_nearest_existing_parent(destination.parent)).free
    if free_bytes < required_free_bytes:
        raise PreflightError("backup root의 여유 공간이 사전 점검 기준보다 부족합니다.")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with _read_only_connection(source_path) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)

    inventory = collect_inventory(destination, read_approved=True)
    if inventory["integrity_check"] != ["ok"]:
        raise PreflightError(f"backup integrity_check 실패: {mask_path(destination)}")
    if (
        inventory["alembic_revision"] != source_inventory["alembic_revision"]
        or inventory["table_count"] != source_inventory["table_count"]
        or inventory["row_counts"] != source_inventory["row_counts"]
    ):
        raise PreflightError(
            f"backup schema 또는 row count 불일치: {mask_path(destination)}"
        )
    return {
        "backup": inventory["database"],
        "created": True,
        "checksum_sha256": inventory["checksum_sha256"],
        "file_size_bytes": inventory["file_size_bytes"],
        "alembic_revision": inventory["alembic_revision"],
        "table_count": inventory["table_count"],
        "integrity_check": inventory["integrity_check"],
        "row_counts_match": True,
    }
