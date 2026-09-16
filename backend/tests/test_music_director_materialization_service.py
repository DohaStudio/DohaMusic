from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from backend.contracts.music_director_proposal import validate_music_director_proposal
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetVersion,
    Job,
    MusicDirectorCandidate,
    MusicDirectorCandidateMaterialization,
    MusicDirectorMaterializationStatus,
    MusicDirectorRun,
    ProjectAsset,
)
from backend.repositories.workspace.asset_repository import AssetRepository
from backend.repositories.workspace.workspace_repository import WorkspaceRepository
from backend.services.workspace.artifact_ingestion_service import ArtifactIngestionService
from backend.services.workspace.music_director_candidate_persistence_service import (
    MusicDirectorCandidatePersistenceService,
    MusicDirectorPersistenceError,
    MusicDirectorPersistenceErrorCode,
)
from backend.services.workspace.music_director_materialization_service import (
    CandidateProposal,
    MaterializeCandidateSetRequest,
    MusicDirectorCandidateMaterializationService,
)
from backend.storage.artifact_publisher import ArtifactPublishError, LocalArtifactPublisher
from backend.storage.artifact_resolver import (
    APPROVED_STORAGE_DOMAINS,
    ArtifactStorageRoots,
)
from backend.tests.test_music_director_candidate_persistence_service import Graph


def _service(tmp_path, count):
    graph = Graph(tmp_path, count=count)
    storage_base = tmp_path / "storage"
    staging = tmp_path / "staging"
    artifact_staging = tmp_path / "artifact-staging"
    for path in [
        *(storage_base / domain for domain in APPROVED_STORAGE_DOMAINS),
        staging,
        artifact_staging,
    ]:
        path.mkdir(parents=True, exist_ok=True)
    roots = ArtifactStorageRoots.from_base_root(storage_base)
    publisher = LocalArtifactPublisher(roots, staging)
    ingestion = ArtifactIngestionService(
        graph.factory,
        artifact_roots=roots,
        staging_root=artifact_staging,
    )
    service = MusicDirectorCandidateMaterializationService(
        graph.factory,
        publisher=publisher,
        artifact_ingestion=ingestion,
        staging_root=staging,
    )
    candidates = []
    with graph.factory() as session:
        for ordinal in range(count):
            proposal = validate_music_director_proposal(
                session,
                {
                    "schema_version": 1,
                    "source_snapshot_id": str(graph.request.composition_snapshot_id),
                    "operations": [
                        {
                            "operation": "set_master_gain",
                            "gain_db": ordinal - 1,
                        }
                    ],
                },
            )
            candidates.append(CandidateProposal(ordinal=ordinal, proposal=proposal))
    request = MaterializeCandidateSetRequest(
        job_id=graph.request.job_id,
        project_id=graph.request.project_id,
        composition_snapshot_id=graph.request.composition_snapshot_id,
        effective_owner_id=graph.request.effective_owner_id,
        claimed_by=graph.request.claimed_by,
        claim_token=graph.request.claim_token,
        candidates=tuple(candidates),
        provider="mock",
        model="mock-v1",
    )
    return graph, service, request, roots, ingestion


def _count(session, entity):
    return session.scalar(select(func.count()).select_from(entity))


LOGICAL_ENTITIES = (
    MusicDirectorRun,
    MusicDirectorCandidate,
    Asset,
    ProjectAsset,
    AssetVersion,
    Artifact,
    ArtifactStorageLocation,
)


def _counts(graph):
    with graph.factory() as session:
        return {entity: _count(session, entity) for entity in LOGICAL_ENTITIES}


def _physical_count(roots):
    return len(list(roots.roots["music"].rglob("proposal-*.json")))


def _fresh_service(graph, tmp_path, roots, ingestion):
    return MusicDirectorCandidateMaterializationService(
        graph.factory,
        publisher=LocalArtifactPublisher(roots, tmp_path / "staging"),
        artifact_ingestion=ingestion,
        staging_root=tmp_path / "staging",
    )


@pytest.mark.parametrize("count", [1, 2, 4])
def test_whole_set_completion_and_response_loss_replay(tmp_path, count) -> None:
    graph, service, request, roots, ingestion = _service(tmp_path, count)
    first = service.materialize(request)
    fresh = _fresh_service(graph, tmp_path, roots, ingestion)
    replay = fresh.materialize(request)

    assert first.run.run_id == replay.run.run_id
    assert tuple(item.candidate_id for item in first.candidates) == tuple(
        item.candidate_id for item in replay.candidates
    )
    with graph.factory() as session:
        assert _count(session, MusicDirectorRun) == 1
        assert _count(session, MusicDirectorCandidate) == count
        assert _count(session, Asset) == count * 2
        assert _count(session, ProjectAsset) == count * 2
        assert _count(session, AssetVersion) == count * 2
        assert _count(session, Artifact) == count * 2
        assert _count(session, MusicDirectorCandidateMaterialization) == count
        materializations = session.scalars(
            select(MusicDirectorCandidateMaterialization).order_by(
                MusicDirectorCandidateMaterialization.ordinal
            )
        ).all()
        assert {item.planned_run_id for item in materializations} == {first.run.run_id}
        assert {item.status for item in materializations} == {
            MusicDirectorMaterializationStatus.COMPLETED.value
        }
    assert len(list(roots.roots["music"].rglob("proposal-*.json"))) == count
    graph.engine.dispose()


class InjectedCrash(RuntimeError):
    pass


@pytest.mark.parametrize(
    ("owner", "method"),
    [
        (AssetRepository, "add_asset"),
        (WorkspaceRepository, "add_project_asset"),
        (AssetRepository, "add_asset_version"),
        (ArtifactIngestionService, "register_trusted_adopted_in_session"),
        (MusicDirectorCandidatePersistenceService, "persist_in_session"),
    ],
)
def test_logical_stage_crash_rolls_back_and_exact_retry_recovers(
    tmp_path, monkeypatch, owner, method
) -> None:
    graph, service, request, roots, ingestion = _service(tmp_path, 2)
    before = _counts(graph)
    original = getattr(owner, method)

    def crash_after_insert(*args, **kwargs):
        original(*args, **kwargs)
        raise InjectedCrash(method)

    monkeypatch.setattr(owner, method, crash_after_insert)
    with pytest.raises(InjectedCrash, match=method):
        service.materialize(request)
    monkeypatch.setattr(owner, method, original)

    assert _counts(graph) == before
    assert _physical_count(roots) == 2
    with graph.factory() as session:
        planned = session.scalars(
            select(MusicDirectorCandidateMaterialization).order_by(
                MusicDirectorCandidateMaterialization.ordinal
            )
        ).all()
        planned_ids = tuple(item.planned_candidate_id for item in planned)
        assert {item.status for item in planned} == {
            MusicDirectorMaterializationStatus.PUBLISHED.value
        }

    recovered = _fresh_service(graph, tmp_path, roots, ingestion).materialize(request)
    assert tuple(item.candidate_id for item in recovered.candidates) == planned_ids
    assert _physical_count(roots) == 2
    after = _counts(graph)
    assert after[MusicDirectorRun] - before[MusicDirectorRun] == 1
    for entity in LOGICAL_ENTITIES[1:]:
        assert after[entity] - before[entity] == 2
    graph.engine.dispose()


def test_mixed_publication_never_commits_partial_logical_set(tmp_path, monkeypatch) -> None:
    graph, service, request, roots, _ = _service(tmp_path, 2)
    before = _counts(graph)
    original = LocalArtifactPublisher.publish_or_adopt
    calls = 0

    def fail_second(publisher, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise InjectedCrash("second publication")
        return original(publisher, *args, **kwargs)

    monkeypatch.setattr(LocalArtifactPublisher, "publish_or_adopt", fail_second)
    with pytest.raises(InjectedCrash, match="second publication"):
        service.materialize(request)

    assert _counts(graph) == before
    with graph.factory() as session:
        statuses = session.scalars(
            select(MusicDirectorCandidateMaterialization.status).order_by(
                MusicDirectorCandidateMaterialization.ordinal
            )
        ).all()
    assert statuses == [
        MusicDirectorMaterializationStatus.PUBLISHED.value,
        MusicDirectorMaterializationStatus.INTENDED.value,
    ]
    assert _physical_count(roots) == 1
    graph.engine.dispose()


@pytest.mark.parametrize("authority", ["cancel", "stale"])
def test_authority_change_before_completion_leaves_no_logical_set(
    tmp_path, monkeypatch, authority
) -> None:
    graph, service, request, roots, _ = _service(tmp_path, 2)
    before = _counts(graph)
    original = MusicDirectorCandidatePersistenceService.persist_in_session

    def change_authority_then_persist(candidate_service, session, persist_request, **kwargs):
        job = session.get(Job, request.job_id)
        assert job is not None
        if authority == "cancel":
            job.cancel_requested_at = datetime.now(UTC)
        else:
            job.claimed_by = "replacement-worker"
        session.flush()
        return original(candidate_service, session, persist_request, **kwargs)

    monkeypatch.setattr(
        MusicDirectorCandidatePersistenceService,
        "persist_in_session",
        change_authority_then_persist,
    )
    expected = (
        MusicDirectorPersistenceErrorCode.CANCELLED
        if authority == "cancel"
        else MusicDirectorPersistenceErrorCode.STALE_CLAIM
    )
    with pytest.raises(MusicDirectorPersistenceError) as error:
        service.materialize(request)
    assert error.value.code is expected
    assert _counts(graph) == before
    assert _physical_count(roots) == 2
    graph.engine.dispose()


def test_terminal_replay_is_cardinality_stable(tmp_path) -> None:
    graph, service, request, roots, ingestion = _service(tmp_path, 2)
    first = service.materialize(request)
    expected_counts = _counts(graph)
    expected_ids = tuple(item.candidate_id for item in first.candidates)
    for _ in range(3):
        replay = _fresh_service(graph, tmp_path, roots, ingestion).materialize(request)
        assert tuple(item.candidate_id for item in replay.candidates) == expected_ids
        assert _counts(graph) == expected_counts
        assert _physical_count(roots) == 2
    graph.engine.dispose()


def test_concurrent_exact_whole_set_converges(tmp_path) -> None:
    graph, service, request, roots, ingestion = _service(tmp_path, 2)
    second = _fresh_service(graph, tmp_path, roots, ingestion)
    before = _counts(graph)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda item: item.materialize(request), (service, second)))

    identities = {
        (
            result.run.run_id,
            tuple(candidate.candidate_id for candidate in result.candidates),
        )
        for result in results
    }
    assert len(identities) == 1
    after = _counts(graph)
    assert after[MusicDirectorRun] - before[MusicDirectorRun] == 1
    for entity in LOGICAL_ENTITIES[1:]:
        assert after[entity] - before[entity] == 2
    assert _physical_count(roots) == 2
    graph.engine.dispose()


def test_concurrent_mismatched_whole_set_fails_closed(tmp_path) -> None:
    graph, service, request, roots, ingestion = _service(tmp_path, 2)
    before = _counts(graph)
    with graph.factory() as session:
        conflicting_proposal = validate_music_director_proposal(
            session,
            {
                "schema_version": 1,
                "source_snapshot_id": str(request.composition_snapshot_id),
                "operations": [{"operation": "set_master_gain", "gain_db": 8}],
            },
        )
    conflicting = replace(
        request,
        candidates=(
            CandidateProposal(ordinal=0, proposal=conflicting_proposal),
            request.candidates[1],
        ),
    )
    second = _fresh_service(graph, tmp_path, roots, ingestion)

    def invoke(candidate_service, candidate_request):
        try:
            return candidate_service.materialize(candidate_request)
        except MusicDirectorPersistenceError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda pair: invoke(*pair),
                ((service, request), (second, conflicting)),
            )
        )
    successes = [item for item in results if not isinstance(item, Exception)]
    conflicts = [item for item in results if isinstance(item, MusicDirectorPersistenceError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].code is MusicDirectorPersistenceErrorCode.CONFLICT
    after = _counts(graph)
    assert after[MusicDirectorRun] - before[MusicDirectorRun] == 1
    for entity in LOGICAL_ENTITIES[1:]:
        assert after[entity] - before[entity] == 2
    assert _physical_count(roots) == 2
    graph.engine.dispose()


def test_completed_replay_rejects_tampered_physical_proposal(tmp_path) -> None:
    graph, service, request, roots, _ = _service(tmp_path, 1)
    service.materialize(request)
    with graph.factory() as session:
        materialization = session.scalar(select(MusicDirectorCandidateMaterialization))
        assert materialization is not None
        payload = roots.roots[materialization.storage_domain].joinpath(
            *materialization.storage_key.split("/")
        )
        materialization_id = materialization.materialization_id
    payload.write_bytes(b"tampered")

    with pytest.raises(ArtifactPublishError):
        service.materialize(request)
    with graph.factory() as session:
        current = session.get(MusicDirectorCandidateMaterialization, materialization_id)
        assert current is not None
        assert current.status == MusicDirectorMaterializationStatus.RECONCILIATION_REQUIRED.value
    graph.engine.dispose()


def test_cancellation_prevents_logical_completion(tmp_path) -> None:
    graph, service, request, _, _ = _service(tmp_path, 1)
    cancelled = replace(request, claimed_by="stale-worker")
    with pytest.raises(MusicDirectorPersistenceError) as error:
        service.materialize(cancelled)
    assert error.value.code is MusicDirectorPersistenceErrorCode.STALE_CLAIM
    with graph.factory() as session:
        assert _count(session, MusicDirectorCandidateMaterialization) == 0
    graph.engine.dispose()
