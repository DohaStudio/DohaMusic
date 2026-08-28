"""단일 사용자 기본 Workspace의 명시적이고 재실행 가능한 Bootstrap CLI."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from backend.core.exceptions import AppError
from backend.db.session import create_database_engine, create_session_factory
from backend.schemas.workspace.bootstrap import WorkspaceBootstrapResult
from backend.services.workspace import WorkspaceService

BOOTSTRAP_TARGET_REVISION = "20260828_0024"
REQUIRED_TRANSITION_TABLES = {
    "workspaces",
    "music_projects",
    "composition_snapshots",
    "project_composition_selections",
}


class WorkspaceBootstrapError(RuntimeError):
    """경로·SQL·credential을 노출하지 않는 Bootstrap 사전 조건 오류."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="단일 사용자 기본 Workspace를 명시적으로 Bootstrap"
    )
    parser.add_argument(
        "--database-url",
        help="명시적 SQLite URL. 생략하면 DATABASE_URL 환경변수를 사용",
    )
    parser.add_argument("--owner-id", type=UUID, required=True)
    parser.add_argument("--name", default="기본 Workspace")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="사전 조건 확인 후 실제 Workspace row 생성을 승인",
    )
    return parser


def resolve_database_url(
    explicit_url: str | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    source = environ if environ is not None else os.environ
    database_url = explicit_url or source.get("DATABASE_URL", "")
    if not database_url.strip():
        raise WorkspaceBootstrapError("명시적 DATABASE_URL이 필요합니다.")
    try:
        parsed = make_url(database_url)
    except ArgumentError as error:
        raise WorkspaceBootstrapError("DATABASE_URL 형식이 유효하지 않습니다.") from error
    if not parsed.drivername.startswith("sqlite"):
        raise WorkspaceBootstrapError("Bootstrap 대상은 명시적 SQLite DB여야 합니다.")
    return database_url


def _ensure_existing_sqlite_target(database_url: str) -> None:
    parsed = make_url(database_url)
    database = parsed.database
    if database in (None, "", ":memory:"):
        return
    if not Path(database).expanduser().is_file():
        raise WorkspaceBootstrapError("명시한 SQLite DB 파일을 찾을 수 없습니다.")


def inspect_bootstrap_target(database_url: str) -> str:
    """Schema를 변경하지 않고 revision과 D1 Transition schema를 확인한다."""

    _ensure_existing_sqlite_target(database_url)
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
            if "alembic_version" not in table_names:
                raise WorkspaceBootstrapError("Alembic revision Table이 없습니다.")
            missing_tables = REQUIRED_TRANSITION_TABLES - table_names
            if missing_tables:
                if "workspaces" in missing_tables:
                    raise WorkspaceBootstrapError("Workspace Table이 없습니다.")
                raise WorkspaceBootstrapError("D1 Transition 필수 Table이 없습니다.")
            revisions = tuple(connection.scalars(text("SELECT version_num FROM alembic_version")))
            if len(revisions) != 1:
                raise WorkspaceBootstrapError("Alembic revision row는 정확히 하나여야 합니다.")
            revision = revisions[0]
            if revision != BOOTSTRAP_TARGET_REVISION:
                raise WorkspaceBootstrapError(
                    f"대상 DB revision은 {BOOTSTRAP_TARGET_REVISION}이어야 합니다."
                )
            _inspect_transition_constraints(inspect(connection))
            return str(revision)
    except WorkspaceBootstrapError:
        raise
    except SQLAlchemyError as error:
        raise WorkspaceBootstrapError("Bootstrap DB 사전 점검에 실패했습니다.") from error
    finally:
        engine.dispose()


def _inspect_transition_constraints(schema_inspector: object) -> None:
    """0018의 same-Project FK와 identity Index를 이름이 아닌 구조로 검증한다."""

    get_pk_constraint = schema_inspector.get_pk_constraint
    get_unique_constraints = schema_inspector.get_unique_constraints
    get_foreign_keys = schema_inspector.get_foreign_keys
    get_indexes = schema_inspector.get_indexes

    primary_key = get_pk_constraint("project_composition_selections")
    if primary_key.get("constrained_columns") != ["project_id"]:
        raise WorkspaceBootstrapError("D1 selection primary key가 유효하지 않습니다.")
    unique_columns = {
        tuple(item.get("column_names") or ())
        for item in get_unique_constraints("project_composition_selections")
    }
    if ("selected_composition_snapshot_id",) not in unique_columns:
        raise WorkspaceBootstrapError("D1 selection unique constraint가 없습니다.")
    foreign_keys = get_foreign_keys("project_composition_selections")
    has_same_project_fk = any(
        tuple(item.get("constrained_columns") or ())
        == ("project_id", "selected_composition_snapshot_id")
        and item.get("referred_table") == "composition_snapshots"
        and tuple(item.get("referred_columns") or ()) == ("project_id", "composition_snapshot_id")
        for item in foreign_keys
    )
    if not has_same_project_fk:
        raise WorkspaceBootstrapError("D1 same-Project foreign key가 없습니다.")
    indexes = get_indexes("composition_snapshots")
    has_identity_index = any(
        item.get("unique")
        and tuple(item.get("column_names") or ()) == ("project_id", "composition_snapshot_id")
        for item in indexes
    )
    if not has_identity_index:
        raise WorkspaceBootstrapError("D1 Snapshot identity index가 없습니다.")


def execute_bootstrap(
    *,
    database_url: str,
    owner_id: UUID,
    name: str,
    apply: bool,
) -> WorkspaceBootstrapResult:
    """dry-run은 DB를 열지 않고, apply만 하나의 Service transaction을 실행한다."""

    normalized_name = name.strip()
    if not normalized_name:
        raise WorkspaceBootstrapError("Workspace 이름은 비어 있을 수 없습니다.")
    if not apply:
        return WorkspaceBootstrapResult(
            status="planned",
            applied=False,
            created=False,
            workspace_id=None,
            name=normalized_name,
            migration_revision=None,
        )

    revision = inspect_bootstrap_target(database_url)
    session_factory = create_session_factory(database_url)
    try:
        result = WorkspaceService(session_factory).bootstrap_default_workspace(
            owner_id=owner_id,
            name=normalized_name,
        )
        return WorkspaceBootstrapResult(
            status="created" if result.created else "existing",
            applied=True,
            created=result.created,
            workspace_id=result.workspace.workspace_id,
            name=result.workspace.name,
            migration_revision=revision,
            transition=asdict(result.transition),
        )
    finally:
        session_factory.kw["bind"].dispose()


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        database_url = resolve_database_url(args.database_url, environ=environ)
        result = execute_bootstrap(
            database_url=database_url,
            owner_id=args.owner_id,
            name=args.name,
            apply=args.apply,
        )
    except (WorkspaceBootstrapError, AppError) as error:
        error_code = error.code if isinstance(error, AppError) else "BOOTSTRAP_BLOCKED"
        message = error.message if isinstance(error, AppError) else str(error)
        print(
            json.dumps(
                {"status": "BLOCKED", "error_code": error_code, "message": message},
                ensure_ascii=False,
            )
        )
        return 2
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
