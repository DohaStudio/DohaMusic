"""CompositionSnapshot 공개 계약과 application foundation 검증."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.core.cursor_pagination import CursorCodec
from backend.core.exceptions import (
    ApplicationValidationError,
    IdempotencyConflictError,
    InvalidCursorError,
    ResourceConflictError,
    ResourceNotFoundError,
    WorkspaceBootstrapRequiredError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.workspace import (
    Asset,
    AssetType,
    AssetVersion,
    CompositionSnapshot,
    MusicProject,
    ProjectAsset,
    SnapshotItem,
    WORKSPACE_ENTITY_CLASSES,
    Workspace,
)
from backend.repositories.workspace import CompositionRepository
from backend.services.workspace import (
    AssetService,
    CompositionService,
    SnapshotItemInput,
    WorkspaceService,
)

SIGNING_KEY = "composition-snapshot-test-signing-key"


@dataclass(frozen=True, slots=True)
class Graph:
    owner_id: UUID
    workspace: Workspace
    project: MusicProject
    asset: Asset
    version: AssetVersion


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'composition-foundation.db').as_posix()}"
    )
    tables = [entity.__table__ for entity in WORKSPACE_ENTITY_CLASSES]
    tables.append(IdempotencyRecord.__table__)
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


@pytest.fixture
def service(session_factory) -> CompositionService:
    return CompositionService(
        session_factory,
        cursor_codec=CursorCodec(SIGNING_KEY),
    )


def _seed_graph(
    session_factory,
    *,
    owner_id: UUID | None = None,
    workspace_id: UUID | None = None,
    global_asset: bool = False,
    attach: bool = True,
    provider_id: str | None = None,
    model_manifest_id: str | None = None,
) -> Graph:
    owner = owner_id or uuid4()
    workspace_service = WorkspaceService(session_factory)
    if workspace_id is None:
        workspace = workspace_service.create_workspace(
            owner_id=owner,
            name=f"작업공간-{uuid4()}",
        )
    else:
        workspace = workspace_service.get_workspace(workspace_id)
    project = workspace_service.create_project(
        workspace_id=workspace.workspace_id,
        title=f"곡-{uuid4()}",
        created_by=owner,
    )
    asset = AssetService(session_factory).create_asset(
        owner_id=owner,
        workspace_id=None if global_asset else workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    version = AssetService(session_factory).create_asset_version(
        asset_id=asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner,
        provider_id=provider_id,
        model_manifest_id=model_manifest_id,
    )
    if attach:
        workspace_service.attach_asset(
            project_id=project.project_id,
            asset_id=asset.asset_id,
            display_order=0,
            role="music",
        )
    return Graph(owner, workspace, project, asset, version)


def _create(
    service: CompositionService,
    graph: Graph,
    *,
    key: str,
    items: list[SnapshotItemInput] | None = None,
    mix: dict | None = None,
    providers: dict | None = None,
    manifests: dict | None = None,
    processing_chain_id: UUID | None = None,
):
    return service.create_snapshot(
        project_id=graph.project.project_id,
        effective_owner_id=graph.owner_id,
        items=items or [SnapshotItemInput(graph.version.asset_version_id, "music", 0)],
        processing_chain_id=processing_chain_id,
        mix_settings_snapshot=mix or {},
        provider_versions=providers or {},
        model_manifest_ids=manifests or {},
        idempotency_key=key,
    )


def test_cursor_pages_are_descending_complete_and_project_bound(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    for number in range(5):
        _create(service, graph, key=f"page-{number}")

    first = service.list_snapshot_page(
        graph.project.project_id,
        effective_owner_id=graph.owner_id,
        limit=2,
    )
    second = service.list_snapshot_page(
        graph.project.project_id,
        effective_owner_id=graph.owner_id,
        cursor=first.next_cursor,
        limit=2,
    )
    third = service.list_snapshot_page(
        graph.project.project_id,
        effective_owner_id=graph.owner_id,
        cursor=second.next_cursor,
        limit=2,
    )
    versions = [
        row.snapshot_version for page in (first, second, third) for row in page.items
    ]
    assert versions == [5, 4, 3, 2, 1]
    assert (
        len(
            {
                row.composition_snapshot_id
                for page in (first, second, third)
                for row in page.items
            }
        )
        == 5
    )
    assert first.has_more and second.has_more
    assert third.has_more is False and third.next_cursor is None

    assert first.next_cursor is not None
    payload, signature = first.next_cursor.split(".")
    replacement = "A" if payload[-1] != "A" else "B"
    tampered = f"{payload[:-1]}{replacement}.{signature}"
    with pytest.raises(InvalidCursorError):
        service.list_snapshot_page(
            graph.project.project_id,
            effective_owner_id=graph.owner_id,
            cursor=tampered,
            limit=2,
        )
    with pytest.raises(InvalidCursorError):
        service.list_snapshot_page(
            graph.project.project_id,
            effective_owner_id=uuid4(),
            cursor=first.next_cursor,
            limit=2,
        )

    other = _seed_graph(
        session_factory,
        owner_id=graph.owner_id,
        workspace_id=graph.workspace.workspace_id,
    )
    with pytest.raises(InvalidCursorError):
        service.list_snapshot_page(
            other.project.project_id,
            effective_owner_id=graph.owner_id,
            cursor=first.next_cursor,
            limit=2,
        )


def test_cursor_handles_empty_tamper_and_malformed(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    empty = service.list_snapshot_page(
        graph.project.project_id,
        effective_owner_id=graph.owner_id,
    )
    assert empty.items == () and empty.next_cursor is None

    _create(service, graph, key="cursor-token")
    page = service.list_snapshot_page(
        graph.project.project_id,
        effective_owner_id=graph.owner_id,
        limit=1,
    )
    assert page.next_cursor is None
    for token in ("not-a-cursor", "x" * 2_049):
        with pytest.raises(InvalidCursorError):
            service.list_snapshot_page(
                graph.project.project_id,
                effective_owner_id=graph.owner_id,
                cursor=token,
                limit=1,
            )


def test_scope_allows_same_workspace_and_owned_global_asset(
    session_factory, service: CompositionService
) -> None:
    normal = _seed_graph(session_factory)
    global_graph = _seed_graph(session_factory, global_asset=True)

    assert _create(service, normal, key="same-workspace").aggregate.snapshot
    assert _create(service, global_graph, key="global-owned").aggregate.snapshot


def test_scope_rejects_cross_owner_cross_workspace_and_detached_membership(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    cross_owner = _seed_graph(session_factory)
    with pytest.raises(ResourceNotFoundError, match="MusicProject"):
        service.list_snapshot_page(
            cross_owner.project.project_id,
            effective_owner_id=graph.owner_id,
        )

    other_workspace = WorkspaceService(session_factory).create_workspace(
        owner_id=graph.owner_id,
        name="다른 작업공간",
    )
    other_asset = AssetService(session_factory).create_asset(
        owner_id=graph.owner_id,
        workspace_id=other_workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    other_version = AssetService(session_factory).create_asset_version(
        asset_id=other_asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    with session_factory.begin() as session:
        session.add(
            ProjectAsset(
                project_id=graph.project.project_id,
                asset_id=other_asset.asset_id,
                role="music",
                display_order=1,
            )
        )
    with pytest.raises(ResourceNotFoundError, match="AssetVersion"):
        _create(
            service,
            graph,
            key="cross-workspace",
            items=[SnapshotItemInput(other_version.asset_version_id, "music", 0)],
        )

    WorkspaceService(session_factory).detach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
    )
    with pytest.raises(ResourceNotFoundError, match="ProjectAsset"):
        _create(service, graph, key="detached")


def test_bootstrap_and_soft_deleted_asset_are_rejected(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    with pytest.raises(WorkspaceBootstrapRequiredError):
        service.list_snapshot_page(
            graph.project.project_id,
            effective_owner_id=uuid4(),
        )

    AssetService(session_factory).delete_asset(graph.asset.asset_id)
    with pytest.raises(ResourceNotFoundError, match="AssetVersion"):
        _create(service, graph, key="deleted-asset")


def test_snapshot_remains_readable_after_project_asset_detach(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    created = _create(service, graph, key="frozen-before-detach")
    WorkspaceService(session_factory).detach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
    )

    aggregate = service.get_snapshot(
        created.aggregate.snapshot.composition_snapshot_id,
        effective_owner_id=graph.owner_id,
    )
    assert [item.asset_version_id for item in aggregate.items] == [
        graph.version.asset_version_id
    ]


@pytest.mark.parametrize("role", ["instrumental", "reference", "mix_source", "MUSIC"])
def test_item_role_vocabulary_is_closed(
    session_factory, service: CompositionService, role: str
) -> None:
    graph = _seed_graph(session_factory)
    with pytest.raises(ApplicationValidationError):
        _create(
            service,
            graph,
            key=f"invalid-role-{role}",
            items=[SnapshotItemInput(graph.version.asset_version_id, role, 0)],
        )


def test_item_validation_rejects_negative_and_duplicates(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    with pytest.raises(ApplicationValidationError):
        _create(
            service,
            graph,
            key="negative-order",
            items=[SnapshotItemInput(graph.version.asset_version_id, "music", -1)],
        )
    with pytest.raises(ResourceConflictError):
        _create(
            service,
            graph,
            key="duplicate-role-order",
            items=[
                SnapshotItemInput(graph.version.asset_version_id, "music", 0),
                SnapshotItemInput(uuid4(), "music", 0),
            ],
        )
    with pytest.raises(ResourceConflictError):
        _create(
            service,
            graph,
            key="duplicate-version-role",
            items=[
                SnapshotItemInput(graph.version.asset_version_id, "stem", 0),
                SnapshotItemInput(graph.version.asset_version_id, "stem", 1),
            ],
        )


def test_version_allocation_is_monotonic_and_project_isolated(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    first = _create(service, graph, key="version-1")
    second = _create(service, graph, key="version-2")
    other = _seed_graph(
        session_factory,
        owner_id=graph.owner_id,
        workspace_id=graph.workspace.workspace_id,
    )
    isolated = _create(service, other, key="version-other-project")

    assert first.aggregate.snapshot.snapshot_version == 1
    assert second.aggregate.snapshot.snapshot_version == 2
    assert isolated.aggregate.snapshot.snapshot_version == 1
    assert first.aggregate.snapshot.created_by == graph.owner_id


def test_version_conflict_retries_are_bounded(
    session_factory, service: CompositionService, monkeypatch
) -> None:
    graph = _seed_graph(session_factory)
    original = CompositionRepository.add_snapshot
    calls = 0

    def collide_once(repository, snapshot):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise IntegrityError("insert", {}, RuntimeError("collision"))
        return original(repository, snapshot)

    monkeypatch.setattr(CompositionRepository, "add_snapshot", collide_once)
    result = _create(service, graph, key="bounded-retry")
    assert calls == 2
    assert result.aggregate.snapshot.snapshot_version == 1


def test_version_conflict_exhaustion_rolls_back_all_attempts(
    session_factory, service: CompositionService, monkeypatch
) -> None:
    graph = _seed_graph(session_factory)
    calls = 0

    def always_collide(repository, snapshot):
        nonlocal calls
        calls += 1
        raise IntegrityError("insert", {}, RuntimeError("collision"))

    monkeypatch.setattr(CompositionRepository, "add_snapshot", always_collide)
    with pytest.raises(ResourceConflictError):
        _create(service, graph, key="bounded-retry-exhausted")

    assert calls == 3
    with session_factory() as session:
        assert len(session.scalars(select(CompositionSnapshot)).all()) == 0
        assert len(session.scalars(select(SnapshotItem)).all()) == 0
        assert len(session.scalars(select(IdempotencyRecord)).all()) == 0


def test_snapshot_item_failure_rolls_back_snapshot_and_idempotency(
    session_factory, service: CompositionService, monkeypatch
) -> None:
    graph = _seed_graph(session_factory)
    second_version = AssetService(session_factory).create_asset_version(
        asset_id=graph.asset.asset_id,
        version_origin="user_edited",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    original = CompositionRepository.add_snapshot_item
    calls = 0

    def fail_second_item(repository, item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("item write failed")
        return original(repository, item)

    monkeypatch.setattr(CompositionRepository, "add_snapshot_item", fail_second_item)
    with pytest.raises(RuntimeError, match="item write failed"):
        _create(
            service,
            graph,
            key="atomic-item-failure",
            items=[
                SnapshotItemInput(graph.version.asset_version_id, "music", 0),
                SnapshotItemInput(second_version.asset_version_id, "music", 1),
            ],
        )

    with session_factory() as session:
        assert len(session.scalars(select(CompositionSnapshot)).all()) == 0
        assert len(session.scalars(select(SnapshotItem)).all()) == 0
        assert len(session.scalars(select(IdempotencyRecord)).all()) == 0


def test_idempotency_replays_and_conflicts_without_duplicate_rows(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    first = _create(service, graph, key="replay-key", mix={"gain": -1})
    replay = _create(service, graph, key="replay-key", mix={"gain": -1})

    assert replay.replayed is True
    assert (
        replay.aggregate.snapshot.composition_snapshot_id
        == first.aggregate.snapshot.composition_snapshot_id
    )
    with pytest.raises(IdempotencyConflictError):
        _create(service, graph, key="replay-key", mix={"gain": -2})
    with session_factory() as session:
        assert len(session.scalars(select(CompositionSnapshot)).all()) == 1
        assert len(session.scalars(select(IdempotencyRecord)).all()) == 1


def test_idempotency_key_is_scoped_by_owner_and_project(
    session_factory, service: CompositionService
) -> None:
    first = _seed_graph(session_factory)
    second = _seed_graph(session_factory)
    result_a = _create(service, first, key="shared-key")
    result_b = _create(service, second, key="shared-key")
    assert (
        result_a.aggregate.snapshot.composition_snapshot_id
        != result_b.aggregate.snapshot.composition_snapshot_id
    )


def test_aggregate_order_and_exact_version_freeze(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    second_version = AssetService(session_factory).create_asset_version(
        asset_id=graph.asset.asset_id,
        version_origin="user_edited",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    created = _create(
        service,
        graph,
        key="aggregate-order",
        items=[
            SnapshotItemInput(second_version.asset_version_id, "vocal", 2),
            SnapshotItemInput(graph.version.asset_version_id, "music", 1),
        ],
    )
    third_version = AssetService(session_factory).create_asset_version(
        asset_id=graph.asset.asset_id,
        version_origin="user_edited",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    aggregate = service.get_snapshot(
        created.aggregate.snapshot.composition_snapshot_id,
        effective_owner_id=graph.owner_id,
    )
    assert [(item.item_role, item.sort_order) for item in aggregate.items] == [
        ("music", 1),
        ("vocal", 2),
    ]
    assert {item.asset_version_id for item in aggregate.items} == {
        graph.version.asset_version_id,
        second_version.asset_version_id,
    }
    assert all(
        item.asset_version_id != third_version.asset_version_id
        for item in aggregate.items
    )


def test_processing_provider_and_manifest_lineage_are_owner_scoped(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(
        session_factory,
        provider_id="audio",
        model_manifest_id="manifest-audio-1",
    )
    other_owner = uuid4()
    chain = CompositionService(session_factory).create_processing_chain(
        name="foreign-chain",
        chain_version="1",
        chain_checksum=str(uuid4()),
        created_by=other_owner,
    )
    with pytest.raises(ResourceNotFoundError, match="ProcessingChain"):
        _create(
            service,
            graph,
            key="foreign-chain",
            providers={"audio": "1.0"},
            manifests={"audio": "manifest-audio-1"},
            processing_chain_id=chain.processing_chain_id,
        )
    with pytest.raises(ApplicationValidationError, match="provider_versions"):
        _create(
            service,
            graph,
            key="missing-provider",
            manifests={"audio": "manifest-audio-1"},
        )
    with pytest.raises(ApplicationValidationError, match="model_manifest_ids"):
        _create(
            service,
            graph,
            key="missing-manifest",
            providers={"audio": "1.0"},
        )
    valid = _create(
        service,
        graph,
        key="complete-lineage",
        providers={"audio": "1.0"},
        manifests={"audio": "manifest-audio-1"},
    )
    assert valid.aggregate.snapshot.provider_versions == {"audio": "1.0"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mix", {"level1": {"level2": {"level3": {"level4": {"too": 1}}}}}),
        ("providers", {"audio": {"version": "1"}}),
        ("manifests", {"audio": ["manifest-1"]}),
    ],
)
def test_json_contract_is_bounded(
    session_factory,
    service: CompositionService,
    field: str,
    value: dict,
) -> None:
    graph = _seed_graph(session_factory)
    kwargs = {"mix": {}, "providers": {}, "manifests": {}}
    kwargs[field] = value
    with pytest.raises(ApplicationValidationError):
        _create(service, graph, key=f"invalid-json-{field}", **kwargs)


def test_repository_and_service_have_no_snapshot_mutation_methods() -> None:
    for target in (CompositionRepository, CompositionService):
        assert not hasattr(target, "update_snapshot")
        assert not hasattr(target, "delete_snapshot")
        assert not hasattr(target, "update_snapshot_item")
        assert not hasattr(target, "delete_snapshot_item")


def test_snapshot_creation_does_not_touch_artifacts(
    session_factory, service: CompositionService
) -> None:
    graph = _seed_graph(session_factory)
    _create(service, graph, key="no-artifact")
    with session_factory() as session:
        assert len(session.scalars(select(SnapshotItem)).all()) == 1
        assert "artifact_id" not in SnapshotItem.__table__.columns
