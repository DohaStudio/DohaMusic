"""WorkingComposition atomic mutation and replay contract tests."""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from backend.api.exception_handlers import register_exception_handlers
from backend.api.v1.dependencies import register_request_id_middleware
from backend.api.v1.routes.working_compositions import router as working_router
from backend.core.exceptions import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    ResourceNotFoundError,
)
from backend.core.idempotency_completion import IdempotencyResultType
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.workspace import (
    WORKSPACE_ENTITY_CLASSES,
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    CompositionClip,
    CompositionSnapshot,
    CompositionSnapshotClip,
    CompositionSnapshotTrack,
    CompositionTrack,
    MusicProject,
    ProjectAsset,
    WorkingComposition,
    Workspace,
)
from backend.repositories.idempotency_repository import IdempotencyRepository
from backend.repositories.workspace import CompositionRepository
from backend.services.workspace import (
    WorkingCompositionError,
    WorkingCompositionErrorCode,
    WorkingCompositionService,
    WorkspaceService,
)
from backend.services.workspace.working_composition_service import _fingerprint


@dataclass(frozen=True, slots=True)
class Graph:
    owner_id: UUID
    workspace_id: UUID
    project_id: UUID
    asset_version_id: UUID


@pytest.fixture(scope="module")
def schema_template(tmp_path_factory) -> Path:
    template = tmp_path_factory.mktemp("working-schema") / "template.db"
    engine = create_database_engine(f"sqlite:///{template.as_posix()}")
    tables = [entity.__table__ for entity in WORKSPACE_ENTITY_CLASSES]
    tables.append(IdempotencyRecord.__table__)
    Base.metadata.create_all(engine, tables=tables)
    engine.dispose()
    return template


@pytest.fixture
def session_factory(tmp_path: Path, schema_template: Path):
    database = tmp_path / "working-composition.db"
    shutil.copy2(schema_template, database)
    engine = create_database_engine(f"sqlite:///{database.as_posix()}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


@pytest.fixture
def graph(session_factory) -> Graph:
    owner_id = uuid4()
    workspace = Workspace(
        workspace_id=uuid4(),
        owner_id=owner_id,
        name="Working Composition",
        lifecycle_status="active",
    )
    project = MusicProject(
        project_id=uuid4(),
        workspace_id=workspace.workspace_id,
        title="Atomic Editing",
        lifecycle_status="active",
        created_by=owner_id,
    )
    asset = Asset(
        asset_id=uuid4(),
        workspace_id=workspace.workspace_id,
        owner_id=owner_id,
        asset_type=AssetType.MUSIC,
        lifecycle_status="active",
    )
    version = AssetVersion(
        asset_version_id=uuid4(),
        asset_id=asset.asset_id,
        version_number=1,
        version_origin="generated",
        settings_snapshot={},
        created_by=owner_id,
    )
    artifact = Artifact(
        artifact_id=uuid4(),
        asset_version_id=version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=1_000,
        duration_us=10_000_000,
        checksum_algorithm="sha256",
        artifact_checksum="a" * 64,
        producer_type="workspace",
        retention_status="active",
    )
    project_asset = ProjectAsset(
        project_asset_id=uuid4(),
        project_id=project.project_id,
        asset_id=asset.asset_id,
        role="music",
        display_order=0,
    )
    with session_factory.begin() as session:
        session.add(workspace)
        session.flush()
        session.add_all([project, asset])
        session.flush()
        session.add(version)
        session.flush()
        session.add_all([artifact, project_asset])
    return Graph(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        project_id=project.project_id,
        asset_version_id=version.asset_version_id,
    )


@pytest.fixture
def service(session_factory) -> WorkingCompositionService:
    return WorkingCompositionService(session_factory)


@pytest.fixture
def working_client(service, session_factory, graph):
    app = FastAPI()
    app.state.working_composition_service = service
    app.state.workspace_service = WorkspaceService(session_factory)
    register_request_id_middleware(app)
    register_exception_handlers(app)
    app.include_router(working_router, prefix="/api/v1")
    with TestClient(app) as client:
        yield client


def _initialize(service: WorkingCompositionService, graph: Graph, key: str = "init"):
    return service.initialize(
        graph.project_id,
        effective_owner_id=graph.owner_id,
        idempotency_key=key,
    )


def _create_track(
    service: WorkingCompositionService,
    graph: Graph,
    working_id: UUID,
    revision: int,
    *,
    key: str = "track",
    name: str = "Audio",
):
    return service.create_track(
        graph.project_id,
        working_composition_id=working_id,
        name=name,
        expected_revision=revision,
        effective_owner_id=graph.owner_id,
        idempotency_key=key,
    )


def _create_clip(
    service: WorkingCompositionService,
    graph: Graph,
    working_id: UUID,
    track_id: UUID,
    revision: int,
    *,
    key: str = "clip",
    timeline_start: str = "0",
):
    return service.create_clip(
        graph.project_id,
        working_composition_id=working_id,
        track_id=track_id,
        source_asset_version_id=graph.asset_version_id,
        timeline_start=timeline_start,
        source_in="0",
        source_out="4",
        expected_revision=revision,
        effective_owner_id=graph.owner_id,
        idempotency_key=key,
    )


def test_first_initialize_creates_revision_zero_and_completion(
    service, session_factory, graph
) -> None:
    result = _initialize(service, graph)
    working_id = result.identities["working_composition_id"]
    assert result.completed_revision == 0
    assert result.replayed is False
    with session_factory() as session:
        working = session.get(WorkingComposition, working_id)
        record = session.scalar(select(IdempotencyRecord))
        assert working is not None and working.revision == 0
        assert record is not None and record.status == "COMPLETED"
        assert record.completed_revision == 0


def test_same_initialize_key_replays_first_identity_and_revision(
    service, session_factory, graph
) -> None:
    first = _initialize(service, graph)
    _create_track(
        service,
        graph,
        first.identities["working_composition_id"],
        0,
        key="later-track",
    )
    replay = _initialize(service, graph)
    assert replay.replayed is True
    assert replay.identities == first.identities
    assert replay.completed_revision == first.completed_revision == 0
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count(WorkingComposition.working_composition_id))
            )
            == 1
        )
        working = session.get(
            WorkingComposition, first.identities["working_composition_id"]
        )
        assert working is not None and working.revision == 1
        assert session.scalar(select(func.count(IdempotencyRecord.id))) == 2


def test_different_initialize_key_is_product_conflict_without_mutation(
    service, session_factory, graph
) -> None:
    first = _initialize(service, graph)
    with pytest.raises(WorkingCompositionError) as caught:
        _initialize(service, graph, "different")
    assert (
        caught.value.code
        is WorkingCompositionErrorCode.WORKING_COMPOSITION_ALREADY_EXISTS
    )
    with session_factory() as session:
        working = session.get(
            WorkingComposition, first.identities["working_composition_id"]
        )
        assert working is not None and working.revision == 0
        assert session.scalar(select(func.count(CompositionTrack.track_id))) == 0
        assert session.scalar(select(func.count(CompositionClip.clip_id))) == 0
        assert session.scalar(select(func.count(IdempotencyRecord.id))) == 1


def test_concurrent_initialize_has_exactly_one_success_and_no_loser_partial_rows(
    service, session_factory, graph
) -> None:
    def attempt(key: str):
        try:
            return _initialize(service, graph, key)
        except WorkingCompositionError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["race-a", "race-b"]))
    successes = [result for result in results if not isinstance(result, Exception)]
    failures = [
        result for result in results if isinstance(result, WorkingCompositionError)
    ]
    assert len(successes) == 1
    assert len(failures) == 1
    assert (
        failures[0].code
        is WorkingCompositionErrorCode.WORKING_COMPOSITION_ALREADY_EXISTS
    )
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count(WorkingComposition.working_composition_id))
            )
            == 1
        )
        assert session.scalar(select(func.count(CompositionTrack.track_id))) == 0
        assert session.scalar(select(func.count(CompositionClip.clip_id))) == 0
        assert session.scalar(select(func.count(IdempotencyRecord.id))) == 1


def test_read_has_no_implicit_create_and_returns_ordered_derived_duration(
    service, session_factory, graph
) -> None:
    with pytest.raises(WorkingCompositionError) as caught:
        service.get_working_composition(
            graph.project_id, effective_owner_id=graph.owner_id
        )
    assert (
        caught.value.code is WorkingCompositionErrorCode.WORKING_COMPOSITION_NOT_FOUND
    )
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count(WorkingComposition.working_composition_id))
            )
            == 0
        )

    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    second = _create_track(service, graph, working_id, 0, key="track-a", name="A")
    first_track = second.identities["track_id"]
    _create_clip(service, graph, working_id, first_track, 1, timeline_start="2")
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert [track.track_order for track in aggregate.tracks] == [0]
    assert aggregate.timeline_duration_us == 6_000_000


def test_track_create_replay_and_fingerprint_conflict(
    service, session_factory, graph
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    first = _create_track(service, graph, working_id, 0)
    replay = _create_track(service, graph, working_id, 0)
    assert replay.replayed is True
    assert replay.identities == first.identities
    assert replay.completed_revision == 1
    with pytest.raises(IdempotencyConflictError):
        _create_track(service, graph, working_id, 0, name="Different")
    with session_factory() as session:
        assert session.scalar(select(func.count(CompositionTrack.track_id))) == 1


def test_revision_stale_rejects_and_success_increments_once(service, graph) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    track = _create_track(service, graph, working_id, 0)
    track_id = track.identities["track_id"]
    renamed = service.rename_track(
        graph.project_id,
        working_composition_id=working_id,
        track_id=track_id,
        name="Renamed",
        expected_revision=1,
        effective_owner_id=graph.owner_id,
    )
    assert renamed.completed_revision == 2
    with pytest.raises(WorkingCompositionError) as caught:
        service.rename_track(
            graph.project_id,
            working_composition_id=working_id,
            track_id=track_id,
            name="Stale",
            expected_revision=1,
            effective_owner_id=graph.owner_id,
        )
    assert (
        caught.value.code
        is WorkingCompositionErrorCode.WORKING_COMPOSITION_REVISION_CONFLICT
    )


def test_clip_create_uses_trusted_duration_overlap_and_adjacency(
    service, graph
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    track = _create_track(service, graph, working_id, 0)
    track_id = track.identities["track_id"]
    first = _create_clip(service, graph, working_id, track_id, 1)
    assert first.completed_revision == 2
    adjacent = _create_clip(
        service,
        graph,
        working_id,
        track_id,
        2,
        key="adjacent",
        timeline_start="4",
    )
    assert adjacent.completed_revision == 3
    with pytest.raises(WorkingCompositionError) as caught:
        _create_clip(
            service,
            graph,
            working_id,
            track_id,
            3,
            key="overlap",
            timeline_start="3.5",
        )
    assert caught.value.code is WorkingCompositionErrorCode.CLIP_OVERLAP


def test_track_not_empty_and_clip_delete_tombstones_only(
    service, session_factory, graph
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    track = _create_track(service, graph, working_id, 0)
    track_id = track.identities["track_id"]
    clip = _create_clip(service, graph, working_id, track_id, 1)
    clip_id = clip.identities["clip_id"]
    with pytest.raises(WorkingCompositionError) as caught:
        service.delete_track(
            graph.project_id,
            working_composition_id=working_id,
            track_id=track_id,
            expected_revision=2,
            effective_owner_id=graph.owner_id,
            idempotency_key="delete-track",
        )
    assert caught.value.code is WorkingCompositionErrorCode.TRACK_NOT_EMPTY
    deleted = service.delete_clip(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        expected_revision=2,
        effective_owner_id=graph.owner_id,
        idempotency_key="delete-clip",
    )
    assert deleted.completed_revision == 3
    with session_factory() as session:
        persisted = session.get(CompositionClip, clip_id)
        assert persisted is not None and persisted.deleted_at is not None
        assert persisted.source_asset_version_id == graph.asset_version_id


def test_split_replay_keeps_first_revision_and_children_after_later_mutation(
    service, graph
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    track = _create_track(service, graph, working_id, 0)
    clip = _create_clip(service, graph, working_id, track.identities["track_id"], 1)
    split = service.split_clip(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip.identities["clip_id"],
        split_at="2",
        expected_revision=2,
        effective_owner_id=graph.owner_id,
        idempotency_key="split",
    )
    service.rename_track(
        graph.project_id,
        working_composition_id=working_id,
        track_id=track.identities["track_id"],
        name="Later",
        expected_revision=3,
        effective_owner_id=graph.owner_id,
    )
    replay = service.split_clip(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip.identities["clip_id"],
        split_at="2.0",
        expected_revision=2,
        effective_owner_id=graph.owner_id,
        idempotency_key="split",
    )
    assert replay.replayed is True
    assert replay.completed_revision == split.completed_revision == 3
    assert replay.identities == split.identities


def test_split_forced_failure_rolls_back_original_children_revision_and_completion(
    service, session_factory, graph, monkeypatch
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    track = _create_track(service, graph, working_id, 0)
    clip = _create_clip(service, graph, working_id, track.identities["track_id"], 1)
    original_add = CompositionRepository.add_composition_clip
    calls = 0

    def fail_second(repository, candidate):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("forced split failure")
        return original_add(repository, candidate)

    monkeypatch.setattr(CompositionRepository, "add_composition_clip", fail_second)
    with pytest.raises(RuntimeError, match="forced split failure"):
        service.split_clip(
            graph.project_id,
            working_composition_id=working_id,
            clip_id=clip.identities["clip_id"],
            split_at="2",
            expected_revision=2,
            effective_owner_id=graph.owner_id,
            idempotency_key="failed-split",
        )
    with session_factory() as session:
        original = session.get(CompositionClip, clip.identities["clip_id"])
        working = session.get(WorkingComposition, working_id)
        assert original is not None and original.deleted_at is None
        assert working is not None and working.revision == 2
        assert session.scalar(select(func.count(CompositionClip.clip_id))) == 1
        assert (
            session.scalar(
                select(func.count(IdempotencyRecord.id)).where(
                    IdempotencyRecord.result_type == "CLIP_SPLIT"
                )
            )
            == 0
        )


def test_checkout_replaces_atomically_and_replays_first_base_revision(
    service, session_factory, graph
) -> None:
    initialized = _initialize(service, graph)
    working_id = initialized.identities["working_composition_id"]
    _create_track(service, graph, working_id, 0)
    snapshot_id = uuid4()
    snapshot_track_id = uuid4()
    canonical_track_id = uuid4()
    canonical_clip_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            CompositionSnapshot(
                composition_snapshot_id=snapshot_id,
                project_id=graph.project_id,
                snapshot_version=1,
                mix_settings_snapshot={},
                provider_versions={},
                model_manifest_ids={},
                created_by=graph.owner_id,
            )
        )
        session.flush()
        session.add(
            CompositionSnapshotTrack(
                snapshot_track_id=snapshot_track_id,
                composition_snapshot_id=snapshot_id,
                canonical_track_id=canonical_track_id,
                track_type="audio",
                name="Snapshot Track",
                track_order=0,
            )
        )
        session.flush()
        session.add(
            CompositionSnapshotClip(
                composition_snapshot_id=snapshot_id,
                snapshot_track_id=snapshot_track_id,
                canonical_clip_id=canonical_clip_id,
                source_asset_version_id=graph.asset_version_id,
                timeline_start=0,
                source_in=0,
                source_out=2_000_000,
                source_duration=10_000_000,
            )
        )
    checkout = service.checkout(
        graph.project_id,
        working_composition_id=working_id,
        composition_snapshot_id=snapshot_id,
        expected_revision=1,
        effective_owner_id=graph.owner_id,
        idempotency_key="checkout",
    )
    assert checkout.completed_revision == 2
    service.rename_track(
        graph.project_id,
        working_composition_id=working_id,
        track_id=canonical_track_id,
        name="Later",
        expected_revision=2,
        effective_owner_id=graph.owner_id,
    )
    replay = service.checkout(
        graph.project_id,
        working_composition_id=working_id,
        composition_snapshot_id=snapshot_id,
        expected_revision=1,
        effective_owner_id=graph.owner_id,
        idempotency_key="checkout",
    )
    assert replay.replayed is True
    assert replay.completed_revision == 2
    assert replay.identities["base_composition_snapshot_id"] == snapshot_id
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert aggregate.working_composition.revision == 3
    assert aggregate.tracks[0].name == "Later"


def test_product_router_exposes_service_results_and_structured_duplicate_error(
    working_client, graph
) -> None:
    base = f"/api/v1/projects/{graph.project_id}/working-composition"
    first = working_client.post(
        f"{base}/initialize",
        json={},
        headers={"Idempotency-Key": "api-init"},
    )
    assert first.status_code == 201
    initialized = first.json()["data"]
    assert initialized["completed_revision"] == 0
    working_id = initialized["working_composition_id"]

    replay = working_client.post(
        f"{base}/initialize",
        json={},
        headers={"Idempotency-Key": "api-init"},
    )
    assert replay.status_code == 201
    assert replay.json()["data"] == {**initialized, "replayed": True}

    duplicate = working_client.post(
        f"{base}/initialize",
        json={},
        headers={"Idempotency-Key": "api-new-key"},
    )
    assert duplicate.status_code == 409
    error = duplicate.json()["error"]
    assert error["error_code"] == "WORKING_COMPOSITION_ALREADY_EXISTS"
    assert not any(
        token in str(error).lower()
        for token in ("storage", "locator", "sqlite", "constraint", "\\")
    )

    created_track = working_client.post(
        f"{base}/tracks",
        json={
            "working_composition_id": working_id,
            "expected_revision": 0,
            "name": "API Track",
        },
        headers={"Idempotency-Key": "api-track"},
    )
    assert created_track.status_code == 201
    assert created_track.json()["data"]["completed_revision"] == 1
    read = working_client.get(base)
    assert read.status_code == 200
    assert read.json()["data"]["tracks"][0]["name"] == "API Track"


def test_router_and_openapi_counts_are_exact_without_new_duplicate_ids() -> None:
    routes = [route for route in working_router.routes if isinstance(route, APIRoute)]
    surface = {
        (method, route.path, route.operation_id)
        for route in routes
        for method in route.methods
    }
    assert surface == {
        (
            "GET",
            "/projects/{project_id}/working-composition",
            "get_working_composition",
        ),
        (
            "POST",
            "/projects/{project_id}/working-composition/initialize",
            "initialize_working_composition",
        ),
        (
            "POST",
            "/projects/{project_id}/working-composition/checkout",
            "checkout_working_composition",
        ),
        (
            "POST",
            "/projects/{project_id}/working-composition/tracks",
            "create_working_composition_track",
        ),
        (
            "PATCH",
            "/projects/{project_id}/working-composition/tracks/reorder",
            "reorder_working_composition_tracks",
        ),
        (
            "PATCH",
            "/projects/{project_id}/working-composition/tracks/{track_id}",
            "rename_working_composition_track",
        ),
        (
            "DELETE",
            "/projects/{project_id}/working-composition/tracks/{track_id}",
            "delete_working_composition_track",
        ),
        (
            "POST",
            "/projects/{project_id}/working-composition/clips",
            "create_working_composition_clip",
        ),
        (
            "PATCH",
            "/projects/{project_id}/working-composition/clips/{clip_id}/move",
            "move_working_composition_clip",
        ),
        (
            "PATCH",
            "/projects/{project_id}/working-composition/clips/{clip_id}/trim-start",
            "trim_working_composition_clip_start",
        ),
        (
            "PATCH",
            "/projects/{project_id}/working-composition/clips/{clip_id}/trim-end",
            "trim_working_composition_clip_end",
        ),
        (
            "POST",
            "/projects/{project_id}/working-composition/clips/{clip_id}/split",
            "split_working_composition_clip",
        ),
        (
            "DELETE",
            "/projects/{project_id}/working-composition/clips/{clip_id}",
            "delete_working_composition_clip",
        ),
    }
    assert len(routes) == 13
    assert len({path for _, path, _ in surface}) == 12
    operation_ids = [operation_id for _, _, operation_id in surface]
    assert len(operation_ids) == len(set(operation_ids)) == 13


def test_track_reorder_is_contiguous_and_empty_track_delete_replays(
    service, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    first = _create_track(service, graph, working_id, 0, key="first", name="First")
    second = _create_track(service, graph, working_id, 1, key="second", name="Second")
    reordered = service.reorder_tracks(
        graph.project_id,
        working_composition_id=working_id,
        ordered_track_ids=[second.identities["track_id"], first.identities["track_id"]],
        expected_revision=2,
        effective_owner_id=graph.owner_id,
    )
    assert reordered.completed_revision == 3
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert [track.track_id for track in aggregate.tracks] == [
        second.identities["track_id"],
        first.identities["track_id"],
    ]
    assert [track.track_order for track in aggregate.tracks] == [0, 1]
    deleted = service.delete_track(
        graph.project_id,
        working_composition_id=working_id,
        track_id=first.identities["track_id"],
        expected_revision=3,
        effective_owner_id=graph.owner_id,
        idempotency_key="delete-empty",
    )
    replay = service.delete_track(
        graph.project_id,
        working_composition_id=working_id,
        track_id=first.identities["track_id"],
        expected_revision=3,
        effective_owner_id=graph.owner_id,
        idempotency_key="delete-empty",
    )
    assert deleted.completed_revision == replay.completed_revision == 4
    assert replay.replayed is True


def test_move_trim_start_trim_end_and_delete_increment_exactly_once(
    service, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    clip_id = _create_clip(service, graph, working_id, track_id, 1).identities[
        "clip_id"
    ]
    moved = service.move_clip(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        timeline_start="1.0000004",
        expected_revision=2,
        effective_owner_id=graph.owner_id,
    )
    trimmed_start = service.trim_clip_start(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        timeline_start="2",
        source_in="1",
        expected_revision=3,
        effective_owner_id=graph.owner_id,
    )
    trimmed_end = service.trim_clip_end(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        source_out="3.5",
        expected_revision=4,
        effective_owner_id=graph.owner_id,
    )
    assert [
        moved.completed_revision,
        trimmed_start.completed_revision,
        trimmed_end.completed_revision,
    ] == [3, 4, 5]
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    clip = aggregate.clips[0]
    assert clip.timeline_start == 2_000_000
    assert clip.source_in == 1_000_000
    assert clip.source_out == 3_500_000


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_project_asset", WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE),
        ("inactive_asset", WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE),
        ("ambiguous", WorkingCompositionErrorCode.SOURCE_ARTIFACT_AMBIGUOUS),
        ("null_duration", WorkingCompositionErrorCode.SOURCE_DURATION_UNAVAILABLE),
    ],
)
def test_clip_source_fail_closed_cases(
    service, session_factory, graph, mutation, expected_code
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    with session_factory.begin() as session:
        version = session.get(AssetVersion, graph.asset_version_id)
        assert version is not None
        asset = session.get(Asset, version.asset_id)
        assert asset is not None
        if mutation == "missing_project_asset":
            project_asset = session.scalar(
                select(ProjectAsset).where(ProjectAsset.project_id == graph.project_id)
            )
            assert project_asset is not None
            project_asset.deleted_at = datetime.now(UTC)
        elif mutation == "inactive_asset":
            asset.lifecycle_status = "archived"
        elif mutation == "ambiguous":
            session.add(
                Artifact(
                    artifact_id=uuid4(),
                    asset_version_id=graph.asset_version_id,
                    artifact_kind="stem",
                    media_type="audio/flac",
                    size_bytes=2_000,
                    duration_us=10_000_000,
                    checksum_algorithm="sha256",
                    artifact_checksum="b" * 64,
                    producer_type="workspace",
                    retention_status="active",
                )
            )
        else:
            artifact = session.scalar(
                select(Artifact).where(
                    Artifact.asset_version_id == graph.asset_version_id
                )
            )
            assert artifact is not None
            artifact.duration_us = None
            artifact.media_type = "audio/mpeg"
    with pytest.raises(WorkingCompositionError) as caught:
        _create_clip(service, graph, working_id, track_id, 1)
    assert caught.value.code is expected_code
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert aggregate.working_composition.revision == 1
    assert aggregate.clips == ()


def test_idempotency_in_progress_is_preserved(service, session_factory, graph) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    key = "busy-track"
    operation = IdempotencyResultType.TRACK_CREATE
    scope = (
        f"working-composition:{graph.owner_id}:{graph.project_id}:"
        f"{working_id}:{operation.value}"
    )
    fingerprint = _fingerprint(
        effective_owner_id=graph.owner_id,
        project_id=graph.project_id,
        working_composition_id=working_id,
        operation=operation.value,
        expected_revision=0,
        target_identity=None,
        body={"name": "Busy"},
    )
    with session_factory.begin() as session:
        session.add(
            IdempotencyRecord(
                scope=scope,
                key_hash=IdempotencyRepository.hash_key(key),
                request_fingerprint=fingerprint,
                status="IN_PROGRESS",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    with pytest.raises(IdempotencyInProgressError):
        _create_track(service, graph, working_id, 0, key=key, name="Busy")


def test_create_rolls_back_row_revision_and_claim_when_completion_fails(
    service, session_factory, graph, monkeypatch
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]

    def fail_completion(*_args, **_kwargs):
        raise RuntimeError("forced completion failure")

    monkeypatch.setattr(IdempotencyRepository, "complete_with_result", fail_completion)
    with pytest.raises(RuntimeError, match="forced completion failure"):
        _create_track(service, graph, working_id, 0, key="failed-track")
    with session_factory() as session:
        working = session.get(WorkingComposition, working_id)
        assert working is not None and working.revision == 0
        assert session.scalar(select(func.count(CompositionTrack.track_id))) == 0
        assert session.scalar(select(func.count(IdempotencyRecord.id))) == 1


def test_concurrent_expected_revision_has_one_success_and_one_conflict(
    service, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]

    def rename(name: str):
        try:
            return service.rename_track(
                graph.project_id,
                working_composition_id=working_id,
                track_id=track_id,
                name=name,
                expected_revision=1,
                effective_owner_id=graph.owner_id,
            )
        except WorkingCompositionError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(rename, ["Concurrent A", "Concurrent B"]))
    successes = [result for result in results if not isinstance(result, Exception)]
    failures = [
        result for result in results if isinstance(result, WorkingCompositionError)
    ]
    assert len(successes) == 1
    assert len(failures) == 1
    assert (
        failures[0].code
        is WorkingCompositionErrorCode.WORKING_COMPOSITION_REVISION_CONFLICT
    )
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert aggregate.working_composition.revision == 2


def test_reorder_forced_failure_restores_original_order(
    service, session_factory, graph, monkeypatch
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    first = _create_track(service, graph, working_id, 0, key="reorder-a")
    second = _create_track(service, graph, working_id, 1, key="reorder-b")
    original = CompositionRepository.reorder_active_composition_tracks

    def fail_after_reorder(repository, target_working_id, order):
        original(repository, target_working_id, order)
        raise RuntimeError("forced reorder failure")

    monkeypatch.setattr(
        CompositionRepository,
        "reorder_active_composition_tracks",
        fail_after_reorder,
    )
    with pytest.raises(RuntimeError, match="forced reorder failure"):
        service.reorder_tracks(
            graph.project_id,
            working_composition_id=working_id,
            ordered_track_ids=[
                second.identities["track_id"],
                first.identities["track_id"],
            ],
            expected_revision=2,
            effective_owner_id=graph.owner_id,
        )
    with session_factory() as session:
        tracks = CompositionRepository(session).list_active_composition_tracks(
            working_id
        )
        working = session.get(WorkingComposition, working_id)
        assert [track.track_id for track in tracks] == [
            first.identities["track_id"],
            second.identities["track_id"],
        ]
        assert working is not None and working.revision == 2


def test_delete_forced_completion_failure_restores_clip_and_revision(
    service, session_factory, graph, monkeypatch
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    clip_id = _create_clip(service, graph, working_id, track_id, 1).identities[
        "clip_id"
    ]

    def fail_completion(*_args, **_kwargs):
        raise RuntimeError("forced delete completion failure")

    monkeypatch.setattr(IdempotencyRepository, "complete_with_result", fail_completion)
    with pytest.raises(RuntimeError, match="forced delete completion failure"):
        service.delete_clip(
            graph.project_id,
            working_composition_id=working_id,
            clip_id=clip_id,
            expected_revision=2,
            effective_owner_id=graph.owner_id,
            idempotency_key="failed-delete",
        )
    with session_factory() as session:
        clip = session.get(CompositionClip, clip_id)
        working = session.get(WorkingComposition, working_id)
        assert clip is not None and clip.deleted_at is None
        assert working is not None and working.revision == 2


def test_checkout_forced_failure_preserves_previous_working_state(
    service, session_factory, graph, monkeypatch
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    old_track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    old_clip_id = _create_clip(service, graph, working_id, old_track_id, 1).identities[
        "clip_id"
    ]
    snapshot_id = uuid4()
    snapshot_track_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            CompositionSnapshot(
                composition_snapshot_id=snapshot_id,
                project_id=graph.project_id,
                snapshot_version=1,
                mix_settings_snapshot={},
                provider_versions={},
                model_manifest_ids={},
                created_by=graph.owner_id,
            )
        )
        session.flush()
        session.add(
            CompositionSnapshotTrack(
                snapshot_track_id=snapshot_track_id,
                composition_snapshot_id=snapshot_id,
                canonical_track_id=uuid4(),
                track_type="audio",
                name="Replacement",
                track_order=0,
            )
        )
        session.flush()
        session.add(
            CompositionSnapshotClip(
                composition_snapshot_id=snapshot_id,
                snapshot_track_id=snapshot_track_id,
                canonical_clip_id=uuid4(),
                source_asset_version_id=graph.asset_version_id,
                timeline_start=0,
                source_in=0,
                source_out=1_000_000,
                source_duration=10_000_000,
            )
        )

    def fail_add(*_args, **_kwargs):
        raise RuntimeError("forced checkout failure")

    monkeypatch.setattr(CompositionRepository, "add_composition_clip", fail_add)
    with pytest.raises(RuntimeError, match="forced checkout failure"):
        service.checkout(
            graph.project_id,
            working_composition_id=working_id,
            composition_snapshot_id=snapshot_id,
            expected_revision=2,
            effective_owner_id=graph.owner_id,
            idempotency_key="failed-checkout",
        )
    with session_factory() as session:
        old_track = session.get(CompositionTrack, old_track_id)
        old_clip = session.get(CompositionClip, old_clip_id)
        working = session.get(WorkingComposition, working_id)
        assert old_track is not None and old_track.deleted_at is None
        assert old_clip is not None and old_clip.deleted_at is None
        assert working is not None and working.revision == 2
        assert working.base_composition_snapshot_id is None
        assert (
            session.scalar(
                select(func.count(IdempotencyRecord.id)).where(
                    IdempotencyRecord.result_type == "WORKING_COMPOSITION_CHECKOUT"
                )
            )
            == 0
        )


def test_checkout_rejects_cross_project_snapshot_without_partial_state(
    service, session_factory, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    other_project_id = uuid4()
    other_snapshot_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            MusicProject(
                project_id=other_project_id,
                workspace_id=graph.workspace_id,
                title="Other Project",
                lifecycle_status="active",
                created_by=graph.owner_id,
            )
        )
        session.flush()
        session.add(
            CompositionSnapshot(
                composition_snapshot_id=other_snapshot_id,
                project_id=other_project_id,
                snapshot_version=1,
                mix_settings_snapshot={},
                provider_versions={},
                model_manifest_ids={},
                created_by=graph.owner_id,
            )
        )

    with pytest.raises(ResourceNotFoundError):
        service.checkout(
            graph.project_id,
            working_composition_id=working_id,
            composition_snapshot_id=other_snapshot_id,
            expected_revision=0,
            effective_owner_id=graph.owner_id,
            idempotency_key="cross-project-checkout",
        )
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert aggregate.working_composition.revision == 0
    assert aggregate.working_composition.base_composition_snapshot_id is None
    with session_factory() as session:
        checkout_results = session.scalar(
            select(func.count(IdempotencyRecord.id)).where(
                IdempotencyRecord.result_type
                == IdempotencyResultType.WORKING_COMPOSITION_CHECKOUT.value
            )
        )
        assert checkout_results == 0


def test_cross_track_overlap_is_allowed_and_exact_asset_version_is_persisted(
    service, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    first_track = _create_track(
        service, graph, working_id, 0, key="cross-track-first"
    ).identities["track_id"]
    second_track = _create_track(
        service, graph, working_id, 1, key="cross-track-second"
    ).identities["track_id"]
    first_clip = _create_clip(
        service,
        graph,
        working_id,
        first_track,
        2,
        key="cross-track-clip-a",
    )
    second_clip = _create_clip(
        service,
        graph,
        working_id,
        second_track,
        3,
        key="cross-track-clip-b",
    )

    assert first_clip.completed_revision == 3
    assert second_clip.completed_revision == 4
    aggregate = service.get_working_composition(
        graph.project_id, effective_owner_id=graph.owner_id
    )
    assert len(aggregate.clips) == 2
    assert {clip.source_asset_version_id for clip in aggregate.clips} == {
        graph.asset_version_id
    }


def test_query_plans_use_existing_working_source_and_snapshot_indexes(
    session_factory, graph
) -> None:
    queries = {
        "working": (
            (
                "SELECT working_composition_id FROM working_compositions "
                "WHERE project_id = :project_id"
            ),
            "sqlite_autoindex_working_compositions",
        ),
        "tracks": (
            (
                "SELECT track_id FROM composition_tracks "
                "WHERE working_composition_id = :working_id AND deleted_at IS NULL "
                "ORDER BY track_order, track_id"
            ),
            "ix_composition_tracks_active_order",
        ),
        "clips": (
            (
                "SELECT clip_id FROM composition_clips "
                "WHERE track_id = :track_id AND deleted_at IS NULL "
                "ORDER BY timeline_start, clip_id"
            ),
            "ix_composition_clips_active_timeline",
        ),
        "clip_count": (
            (
                "SELECT count(clip_id) FROM composition_clips "
                "WHERE working_composition_id = :working_id "
                "AND track_id = :track_id AND deleted_at IS NULL"
            ),
            "ix_composition_clips_active_timeline",
        ),
        "artifacts": (
            (
                "SELECT artifact_id FROM artifacts "
                "WHERE asset_version_id = :version_id "
                "ORDER BY created_at, artifact_id"
            ),
            "ix_artifacts_version_created",
        ),
        "snapshot_tracks": (
            (
                "SELECT snapshot_track_id FROM composition_snapshot_tracks "
                "WHERE composition_snapshot_id = :snapshot_id "
                "ORDER BY track_order, snapshot_track_id"
            ),
            "ix_composition_snapshot_tracks_order",
        ),
        "snapshot_clips": (
            (
                "SELECT snapshot_clip_id FROM composition_snapshot_clips "
                "WHERE snapshot_track_id = :snapshot_track_id "
                "ORDER BY timeline_start, snapshot_clip_id"
            ),
            "ix_composition_snapshot_clips_timeline",
        ),
        "snapshot_checkout_clips": (
            (
                "SELECT snapshot_clip_id FROM composition_snapshot_clips "
                "WHERE composition_snapshot_id = :snapshot_id "
                "ORDER BY snapshot_track_id, timeline_start, snapshot_clip_id"
            ),
            "sqlite_autoindex_composition_snapshot_clips",
        ),
    }
    parameters = {
        "project_id": str(graph.project_id).replace("-", ""),
        "working_id": str(uuid4()).replace("-", ""),
        "track_id": str(uuid4()).replace("-", ""),
        "version_id": str(graph.asset_version_id).replace("-", ""),
        "snapshot_id": str(uuid4()).replace("-", ""),
        "snapshot_track_id": str(uuid4()).replace("-", ""),
    }
    with session_factory() as session:
        for query, expected_index in queries.values():
            plan = " ".join(
                str(row[-1])
                for row in session.execute(
                    text(f"EXPLAIN QUERY PLAN {query}"), parameters
                )
            )
            assert expected_index in plan
