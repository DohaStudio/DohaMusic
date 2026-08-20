"""D1 Composition Transition의 무선택·멱등·복구 계약 검증."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from backend.cli.workspace_bootstrap import (
    BOOTSTRAP_TARGET_REVISION,
    WorkspaceBootstrapError,
    execute_bootstrap,
    inspect_bootstrap_target,
)
from backend.core.exceptions import InvalidStateError
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.models.workspace import (
    CompositionSnapshot,
    MusicProject,
    ProjectCompositionSelection,
)
from backend.repositories.workspace import CompositionRepository
from backend.repositories.workspace.composition_repository import (
    ProjectCompositionTransitionState,
)
from backend.services.workspace import CompositionService, WorkspaceService
from backend.services.workspace.workspace_service import (
    _summarize_composition_transition,
)


@pytest.fixture(scope="module")
def transition_database_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("d1-transition-template") / "template.db"
    engine = create_database_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        )
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": BOOTSTRAP_TARGET_REVISION},
        )
    engine.dispose()
    return path


@pytest.fixture
def database_url(tmp_path: Path, transition_database_template: Path) -> str:
    path = tmp_path / "transition.db"
    shutil.copyfile(transition_database_template, path)
    return f"sqlite:///{path.as_posix()}"


def _bootstrap_project(
    database_url: str,
    *,
    owner_id: UUID | None = None,
    lifecycle_status: str = "active",
) -> tuple[UUID, UUID]:
    owner = owner_id or uuid4()
    bootstrap = execute_bootstrap(
        database_url=database_url,
        owner_id=owner,
        name="기본 Workspace",
        apply=True,
    )
    assert bootstrap.workspace_id is not None
    factory = create_session_factory(database_url)
    try:
        project = WorkspaceService(factory).create_project(
            workspace_id=bootstrap.workspace_id,
            title=f"Project-{uuid4()}",
            created_by=owner,
            lifecycle_status=lifecycle_status,
        )
        return owner, project.project_id
    finally:
        factory.kw["bind"].dispose()


def _add_snapshot(database_url: str, project_id: UUID, owner_id: UUID) -> UUID:
    factory = create_session_factory(database_url)
    try:
        with factory() as session, session.begin():
            repository = CompositionRepository(session)
            snapshot = repository.add_snapshot(
                CompositionSnapshot(
                    project_id=project_id,
                    snapshot_version=repository.get_next_snapshot_version(project_id),
                    mix_settings_snapshot={},
                    provider_versions={},
                    model_manifest_ids={},
                    created_by=owner_id,
                )
            )
            return snapshot.composition_snapshot_id
    finally:
        factory.kw["bind"].dispose()


def _selection_count(database_url: str) -> int:
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            return int(
                session.scalar(
                    select(func.count()).select_from(ProjectCompositionSelection)
                )
                or 0
            )
    finally:
        engine.dispose()


def test_transition_schema_gate_accepts_0018(database_url: str) -> None:
    assert inspect_bootstrap_target(database_url) == BOOTSTRAP_TARGET_REVISION


def test_transition_schema_gate_requires_selection_table(database_url: str) -> None:
    engine = create_database_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE project_composition_selections"))
    engine.dispose()

    with pytest.raises(WorkspaceBootstrapError, match="D1 Transition"):
        inspect_bootstrap_target(database_url)


def test_empty_workspace_transition_is_ready(database_url: str) -> None:
    result = execute_bootstrap(
        database_url=database_url,
        owner_id=uuid4(),
        name="기본 Workspace",
        apply=True,
    )

    assert result.transition is not None
    assert result.transition.status == "ready"
    assert result.transition.project_count == 0
    assert result.transition.expected_mutation_row_count == 0


def test_project_without_snapshot_remains_empty(database_url: str) -> None:
    owner_id, _ = _bootstrap_project(database_url)

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="무시되는 이름",
        apply=True,
    )

    assert result.transition is not None
    assert result.transition.empty_project_count == 1
    assert result.transition.selection_required_project_count == 0
    assert _selection_count(database_url) == 0


@pytest.mark.parametrize("snapshot_count", [1, 3])
def test_snapshot_without_authority_is_never_auto_selected(
    database_url: str, snapshot_count: int
) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    for _ in range(snapshot_count):
        _add_snapshot(database_url, project_id, owner_id)

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    assert result.transition is not None
    assert result.transition.status == "selection_required"
    assert result.transition.selection_required_project_count == 1
    assert result.transition.authority == "NO_PREEXISTING_SELECTION_AUTHORITY"
    assert result.transition.authoritative_backfill_project_count == 0
    assert result.transition.expected_mutation_row_count == 0
    assert _selection_count(database_url) == 0


def test_existing_valid_selection_is_preserved(database_url: str) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    snapshot_id = _add_snapshot(database_url, project_id, owner_id)
    factory = create_session_factory(database_url)
    try:
        CompositionService(factory).set_project_selection(
            project_id,
            selected_snapshot_id=snapshot_id,
            effective_owner_id=owner_id,
        )
    finally:
        factory.kw["bind"].dispose()

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    assert result.transition is not None
    assert result.transition.status == "ready"
    assert result.transition.already_selected_project_count == 1
    assert _selection_count(database_url) == 1


def test_bootstrap_and_zero_backfill_are_idempotent_three_times(
    database_url: str,
) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    _add_snapshot(database_url, project_id, owner_id)

    results = [
        execute_bootstrap(
            database_url=database_url,
            owner_id=owner_id,
            name="기본 Workspace",
            apply=True,
        )
        for _ in range(3)
    ]

    assert results[0].transition == results[1].transition == results[2].transition
    assert _selection_count(database_url) == 0


def test_restart_reopen_preserves_transition_state(database_url: str) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    _add_snapshot(database_url, project_id, owner_id)
    first = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    second = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    assert second.transition == first.transition
    assert second.workspace_id == first.workspace_id


def test_inventory_failure_rolls_back_new_workspace(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_inventory(
        repository: CompositionRepository, workspace_id: UUID
    ) -> list[ProjectCompositionTransitionState]:
        raise RuntimeError("injected transition failure")

    monkeypatch.setattr(CompositionRepository, "list_transition_states", fail_inventory)

    with pytest.raises(RuntimeError, match="injected transition failure"):
        execute_bootstrap(
            database_url=database_url,
            owner_id=uuid4(),
            name="기본 Workspace",
            apply=True,
        )

    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(MusicProject)) == 0
            assert session.scalar(text("SELECT count(*) FROM workspaces")) == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("selected_project", [None, uuid4()])
def test_dangling_or_cross_project_selection_fails_closed(
    selected_project: UUID | None,
) -> None:
    project_id = uuid4()
    with pytest.raises(InvalidStateError):
        _summarize_composition_transition(
            [
                ProjectCompositionTransitionState(
                    project_id=project_id,
                    has_snapshots=True,
                    selected_snapshot_id=uuid4(),
                    selected_snapshot_project_id=selected_project,
                )
            ]
        )


def test_no_authority_summary_has_no_ambiguous_or_mutation_rows() -> None:
    summary = _summarize_composition_transition(
        [
            ProjectCompositionTransitionState(uuid4(), False, None, None),
            ProjectCompositionTransitionState(uuid4(), True, None, None),
        ]
    )

    assert summary.authority == "NO_PREEXISTING_SELECTION_AUTHORITY"
    assert summary.empty_project_count == 1
    assert summary.selection_required_project_count == 1
    assert summary.ambiguous_authority_project_count == 0
    assert summary.invalid_cross_project_selection_count == 0
    assert summary.expected_mutation_row_count == 0


def test_transition_inventory_is_one_batch_query(database_url: str) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    _add_snapshot(database_url, project_id, owner_id)
    engine = create_database_engine(database_url)
    statements: list[tuple[str, object]] = []

    def record_statement(*args: object) -> None:
        statements.append((str(args[2]), args[3]))

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with Session(engine) as session:
            workspace_id = session.scalar(select(MusicProject.workspace_id))
            assert workspace_id is not None
            statements.clear()
            states = CompositionRepository(session).list_transition_states(workspace_id)
            assert len(statements) == 1
            sql, parameters = statements[0]
            plan = session.connection().exec_driver_sql(
                f"EXPLAIN QUERY PLAN {sql}", parameters
            )
            plan_details = [str(row[3]) for row in plan]
        assert len(states) == 1
        assert not any("TEMP B-TREE" in detail for detail in plan_details), plan_details
        assert any("ix_music_projects_workspace" in detail for detail in plan_details)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
        engine.dispose()


def test_transition_preserves_aggregate_empty_selection_required_and_ready(
    database_url: str,
) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    factory = create_session_factory(database_url)
    try:
        service = CompositionService(factory)
        assert (
            service.get_project_composition(
                project_id, effective_owner_id=owner_id
            ).state
            == "empty"
        )
        snapshot_id = _add_snapshot(database_url, project_id, owner_id)
        assert (
            service.get_project_composition(
                project_id, effective_owner_id=owner_id
            ).state
            == "selection_required"
        )
        service.set_project_selection(
            project_id,
            selected_snapshot_id=snapshot_id,
            effective_owner_id=owner_id,
        )
        assert (
            service.get_project_composition(
                project_id, effective_owner_id=owner_id
            ).state
            == "ready"
        )
    finally:
        factory.kw["bind"].dispose()


def test_soft_deleted_project_is_outside_active_transition_inventory(
    database_url: str,
) -> None:
    owner_id, project_id = _bootstrap_project(database_url)
    factory = create_session_factory(database_url)
    try:
        WorkspaceService(factory).delete_project(project_id)
    finally:
        factory.kw["bind"].dispose()

    result = execute_bootstrap(
        database_url=database_url,
        owner_id=owner_id,
        name="기본 Workspace",
        apply=True,
    )

    assert result.transition is not None
    assert result.transition.project_count == 0
