"""단일 사용자 기본 Workspace Bootstrap의 명시성·멱등성·안전성 검증."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.cli.workspace_bootstrap import (
    BOOTSTRAP_TARGET_REVISION,
    WorkspaceBootstrapError,
    execute_bootstrap,
    inspect_bootstrap_target,
    resolve_database_url,
)
from backend.core.exceptions import InvalidStateError, ResourceConflictError
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.models.project import Project
from backend.models.workspace import Workspace
from backend.repositories.workspace import WorkspaceRepository
from backend.services.workspace import WorkspaceService


def _database_url(
    path: Path,
    *,
    revision: str = BOOTSTRAP_TARGET_REVISION,
) -> str:
    url = f"sqlite:///{path.as_posix()}"
    engine = create_database_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )
        connection.execute(
            text(
                "INSERT INTO projects "
                "(id, title, description, is_default, created_at, updated_at) "
                "VALUES ('runtime-marker', 'Runtime', NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()
    return url


def _workspace_count(database_url: str) -> int:
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            return int(session.scalar(select(func.count()).select_from(Workspace)) or 0)
    finally:
        engine.dispose()


def _runtime_project_count(database_url: str) -> int:
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            return int(session.scalar(select(func.count()).select_from(Project)) or 0)
    finally:
        engine.dispose()


def test_dry_run_does_not_open_or_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "does-not-exist.db"

    result = execute_bootstrap(
        database_url=f"sqlite:///{database_path.as_posix()}",
        owner_id=uuid4(),
        name="기본 Workspace",
        apply=False,
    )

    assert result.status == "planned"
    assert result.applied is False
    assert not database_path.exists()


def test_explicit_database_url_and_owner_are_required() -> None:
    with pytest.raises(WorkspaceBootstrapError, match="DATABASE_URL"):
        resolve_database_url(None, environ={})

    with pytest.raises(WorkspaceBootstrapError, match="형식"):
        resolve_database_url("not-a-database-url", environ={})


def test_dry_run_rejects_empty_workspace_name_without_database_access(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "still-does-not-exist.db"

    with pytest.raises(WorkspaceBootstrapError, match="이름"):
        execute_bootstrap(
            database_url=f"sqlite:///{database_path.as_posix()}",
            owner_id=uuid4(),
            name="   ",
            apply=False,
        )

    assert not database_path.exists()


def test_wrong_revision_is_blocked_without_workspace_change(tmp_path: Path) -> None:
    database_url = _database_url(
        tmp_path / "wrong-revision.db", revision="20260801_0011"
    )

    with pytest.raises(WorkspaceBootstrapError, match=BOOTSTRAP_TARGET_REVISION):
        execute_bootstrap(
            database_url=database_url,
            owner_id=uuid4(),
            name="기본 Workspace",
            apply=True,
        )

    assert _workspace_count(database_url) == 0


def test_current_source_head_passes_revision_gate_without_bootstrap(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path / "current-revision.db")

    assert inspect_bootstrap_target(database_url) == "20260809_0016"
    assert _workspace_count(database_url) == 0


@pytest.mark.parametrize(
    "revision",
    [
        "20260807_0013",
        "20260807_0014",
        "20260808_0015",
        "20999999_9999",
        "not-a-revision",
    ],
)
def test_non_target_revision_is_blocked_without_bootstrap(
    tmp_path: Path,
    revision: str,
) -> None:
    database_url = _database_url(
        tmp_path / f"non-target-{revision}.db",
        revision=revision,
    )

    with pytest.raises(WorkspaceBootstrapError, match=BOOTSTRAP_TARGET_REVISION):
        inspect_bootstrap_target(database_url)

    assert _workspace_count(database_url) == 0


def test_missing_alembic_revision_table_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "missing-alembic-version.db"
    database_url = f"sqlite:///{path.as_posix()}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    with pytest.raises(WorkspaceBootstrapError, match="Alembic revision Table"):
        inspect_bootstrap_target(database_url)


@pytest.mark.parametrize("revision_count", [0, 2])
def test_revision_row_count_must_be_exactly_one(
    tmp_path: Path,
    revision_count: int,
) -> None:
    database_url = _database_url(tmp_path / f"revision-rows-{revision_count}.db")
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
        for index in range(revision_count):
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {
                    "revision": (
                        BOOTSTRAP_TARGET_REVISION if index == 0 else "20260808_0015"
                    )
                },
            )
    engine.dispose()

    with pytest.raises(WorkspaceBootstrapError, match="정확히 하나"):
        inspect_bootstrap_target(database_url)

    assert _workspace_count(database_url) == 0


def test_missing_workspace_table_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "missing-workspaces.db"
    database_url = f"sqlite:///{path.as_posix()}"
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        )
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": BOOTSTRAP_TARGET_REVISION},
        )
    engine.dispose()

    with pytest.raises(WorkspaceBootstrapError, match="Workspace Table"):
        execute_bootstrap(
            database_url=database_url,
            owner_id=uuid4(),
            name="기본 Workspace",
            apply=True,
        )


def test_apply_creates_once_and_reuses_same_workspace(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "bootstrap.db")
    owner_id = uuid4()

    first = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="  나의 Workspace  ",
        apply=True,
    )
    second = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="다른 요청 이름",
        apply=True,
    )

    assert first.status == "created"
    assert first.created is True
    assert first.name == "나의 Workspace"
    assert second.status == "existing"
    assert second.created is False
    assert second.workspace_id == first.workspace_id
    assert _workspace_count(database_url) == 1
    assert _runtime_project_count(database_url) == 1


def test_soft_deleted_workspace_is_not_restored(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "soft-delete.db")
    owner_id = uuid4()
    factory = create_session_factory(database_url)
    service = WorkspaceService(factory)
    original = service.create_workspace(owner_id=owner_id, name="기본 Workspace")
    service.delete_workspace(original.workspace_id)
    factory.kw["bind"].dispose()

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    assert result.created is True
    assert result.workspace_id != original.workspace_id


def test_multiple_active_workspaces_are_blocked(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "multiple.db")
    owner_id = uuid4()
    factory = create_session_factory(database_url)
    service = WorkspaceService(factory)
    service.create_workspace(owner_id=owner_id, name="첫 번째")
    service.create_workspace(owner_id=owner_id, name="두 번째")
    factory.kw["bind"].dispose()

    with pytest.raises(InvalidStateError):
        execute_bootstrap(
            database_url=database_url,
            owner_id=owner_id,
            name="기본 Workspace",
            apply=True,
        )

    assert _workspace_count(database_url) == 2


def test_existing_workspace_for_another_owner_is_blocked(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "owner-conflict.db")
    factory = create_session_factory(database_url)
    WorkspaceService(factory).create_workspace(
        owner_id=uuid4(),
        name="기존 Workspace",
    )
    factory.kw["bind"].dispose()

    with pytest.raises(ResourceConflictError, match="owner"):
        execute_bootstrap(
            database_url=database_url,
            owner_id=uuid4(),
            name="기본 Workspace",
            apply=True,
        )

    assert _workspace_count(database_url) == 1


def test_failure_rolls_back_created_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = _database_url(tmp_path / "rollback.db")
    original_add = WorkspaceRepository.add_workspace

    def fail_after_flush(
        repository: WorkspaceRepository, workspace: Workspace
    ) -> Workspace:
        original_add(repository, workspace)
        raise RuntimeError("injected bootstrap failure")

    monkeypatch.setattr(WorkspaceRepository, "add_workspace", fail_after_flush)

    with pytest.raises(RuntimeError, match="injected bootstrap failure"):
        execute_bootstrap(
            database_url=database_url,
            owner_id=uuid4(),
            name="기본 Workspace",
            apply=True,
        )

    assert _workspace_count(database_url) == 0
    assert _runtime_project_count(database_url) == 1


def test_owner_id_is_stable_and_not_generated_by_bootstrap(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "owner.db")
    owner_id = UUID("11111111-1111-4111-8111-111111111111")

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            workspace = session.get(Workspace, result.workspace_id)
            assert workspace is not None
            assert workspace.owner_id == owner_id
    finally:
        engine.dispose()
