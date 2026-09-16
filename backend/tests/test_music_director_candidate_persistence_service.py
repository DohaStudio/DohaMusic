from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetType,
    AssetVersion,
    CompositionSnapshot,
    Job,
    JobStatus,
    MusicDirectorCandidate,
    MusicDirectorRun,
    MusicProject,
    ProjectAsset,
    WorkingComposition,
    Workspace,
)
from backend.services.workspace.music_director_candidate_persistence_service import (
    CandidatePersistenceFact,
    MusicDirectorCandidatePersistenceService,
    MusicDirectorPersistenceError,
    MusicDirectorPersistenceErrorCode,
    PersistCandidateSetRequest,
)


class Graph:
    def __init__(self, tmp_path, count=2):
        self.engine = create_database_engine(f"sqlite:///{(tmp_path / 'director.db').as_posix()}")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.owner, self.token = uuid4(), uuid4()
        with self.factory() as session, session.begin():
            workspace = Workspace(owner_id=self.owner, name="Director", lifecycle_status="active")
            session.add(workspace)
            session.flush()
            project = MusicProject(
                workspace_id=workspace.workspace_id,
                title="Project",
                lifecycle_status="active",
                created_by=self.owner,
            )
            session.add(project)
            session.flush()
            snapshot = CompositionSnapshot(
                project_id=project.project_id,
                snapshot_version=1,
                mix_settings_snapshot={},
                provider_versions={},
                model_manifest_ids={},
                created_by=self.owner,
            )
            session.add(snapshot)
            session.flush()
            working = WorkingComposition(
                project_id=project.project_id,
                base_composition_snapshot_id=snapshot.composition_snapshot_id,
                mix_settings={},
                revision=7,
            )
            session.add(working)
            job = Job(
                project_id=project.project_id,
                workspace_id=workspace.workspace_id,
                composition_snapshot_id=snapshot.composition_snapshot_id,
                job_type="music_director",
                status=JobStatus.RUNNING,
                api_contract_version="1",
                settings_snapshot={
                    "music_intent": {"instruction": "variations", "candidate_count": count}
                },
                requested_by=self.owner,
                claimed_by="worker",
                claim_token=self.token,
                lease_expires_at=datetime.now(UTC) + timedelta(hours=1),
                attempt=1,
            )
            session.add(job)
            session.flush()
            facts = []
            for ordinal in range(count):
                digest = f"{ordinal + 1:064x}"
                asset = Asset(
                    workspace_id=workspace.workspace_id,
                    owner_id=self.owner,
                    asset_type=AssetType.CANDIDATE,
                    lifecycle_status="active",
                )
                session.add(asset)
                session.flush()
                version = AssetVersion(
                    asset_id=asset.asset_id,
                    version_number=1,
                    version_origin="music_director",
                    settings_snapshot={},
                    created_by=self.owner,
                )
                session.add(version)
                session.flush()
                session.add(
                    ProjectAsset(
                        project_id=project.project_id,
                        asset_id=asset.asset_id,
                        role="music_director_candidate",
                        display_order=ordinal,
                    )
                )
                artifact = Artifact(
                    asset_version_id=version.asset_version_id,
                    artifact_kind="music_director_proposal",
                    media_type="application/json",
                    size_bytes=10,
                    checksum_algorithm="sha256",
                    artifact_checksum=digest,
                    producer_type="music_director",
                    retention_status="active",
                )
                session.add(artifact)
                session.flush()
                session.add(
                    ArtifactStorageLocation(
                        artifact_id=artifact.artifact_id,
                        storage_backend="local",
                        storage_domain="music",
                        storage_key=f"candidate/{artifact.artifact_id}",
                        locator_version=1,
                    )
                )
                facts.append(
                    CandidatePersistenceFact(
                        ordinal,
                        digest,
                        version.asset_version_id,
                        artifact.artifact_id,
                        provider="mock",
                        model="v1",
                    )
                )
            self.request = PersistCandidateSetRequest(
                job.job_id,
                project.project_id,
                snapshot.composition_snapshot_id,
                self.owner,
                "worker",
                self.token,
                tuple(facts),
            )
            self.working_id = working.working_composition_id

    def count(self, entity):
        with self.factory() as session:
            return session.scalar(select(func.count()).select_from(entity)) or 0

    def revision(self):
        with self.factory() as session:
            return session.get(WorkingComposition, self.working_id).revision


@pytest.fixture
def graph(tmp_path):
    graph = Graph(tmp_path)
    yield graph
    graph.engine.dispose()


def test_persist_and_fresh_response_loss_replay(graph):
    first = MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    replay = MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    assert not first.replayed and replay.replayed
    assert replay.run.run_id == first.run.run_id
    assert [x.candidate_id for x in replay.candidates] == [x.candidate_id for x in first.candidates]
    assert (
        graph.count(MusicDirectorRun),
        graph.count(MusicDirectorCandidate),
        graph.revision(),
    ) == (1, 2, 7)


@pytest.mark.parametrize("count", [1, 2, 4])
def test_cardinality_and_order(tmp_path, count):
    graph = Graph(tmp_path, count)
    result = MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    assert [item.ordinal for item in result.candidates] == list(range(count))
    graph.engine.dispose()


@pytest.mark.parametrize("ordinals", [(), (0, 1, 2, 3, 4), (1, 2), (0, 2), (0, 0)])
def test_invalid_candidate_shape(graph, ordinals):
    facts = tuple(replace(graph.request.candidates[0], ordinal=value) for value in ordinals)
    with pytest.raises(MusicDirectorPersistenceError) as error:
        MusicDirectorCandidatePersistenceService(graph.factory).persist(
            replace(graph.request, candidates=facts)
        )
    assert error.value.code is MusicDirectorPersistenceErrorCode.INVALID_CARDINALITY
    assert graph.count(MusicDirectorRun) == 0


def test_conflicting_replay_is_fail_closed(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    service.persist(graph.request)
    facts = (
        replace(graph.request.candidates[0], proposal_digest="f" * 64),
        graph.request.candidates[1],
    )
    with pytest.raises(MusicDirectorPersistenceError) as error:
        service.persist(replace(graph.request, candidates=facts))
    assert error.value.code is MusicDirectorPersistenceErrorCode.CONFLICT
    assert graph.count(MusicDirectorCandidate) == 2


def test_claim_and_cancellation_guards(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    with pytest.raises(MusicDirectorPersistenceError) as stale:
        service.persist(replace(graph.request, claim_token=uuid4()))
    assert stale.value.code is MusicDirectorPersistenceErrorCode.STALE_CLAIM
    with graph.factory() as session, session.begin():
        session.get(Job, graph.request.job_id).cancel_requested_at = datetime.now(UTC)
    with pytest.raises(MusicDirectorPersistenceError) as cancelled:
        service.persist(graph.request)
    assert cancelled.value.code is MusicDirectorPersistenceErrorCode.CANCELLED
    assert graph.count(MusicDirectorRun) == 0


def test_selection_change_replay_stale_and_reject(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    persisted = service.persist(graph.request)
    first, second = persisted.candidates
    selected = service.select(
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=first.candidate_id,
        expected_version=0,
    )
    replay = service.select(
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=first.candidate_id,
        expected_version=0,
    )
    assert selected.version == replay.version == 1
    changed = service.select(
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=second.candidate_id,
        expected_version=1,
    )
    assert changed.selected_candidate_id == second.candidate_id
    with pytest.raises(MusicDirectorPersistenceError) as stale:
        service.select(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=first.candidate_id,
            expected_version=1,
        )
    assert stale.value.code is MusicDirectorPersistenceErrorCode.STALE_SELECTION
    assert (
        service.reject(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=first.candidate_id,
        ).status
        == "rejected"
    )
    with pytest.raises(MusicDirectorPersistenceError):
        service.select(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=first.candidate_id,
            expected_version=2,
        )
    assert graph.revision() == 7


def test_concurrent_exact_persistence_converges(graph):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: MusicDirectorCandidatePersistenceService(graph.factory).persist(
                    graph.request
                ),
                range(2),
            )
        )
    assert len({result.run.run_id for result in results}) == 1
    assert graph.count(MusicDirectorRun) == 1
    assert graph.count(MusicDirectorCandidate) == 2


def test_invalid_lineage_and_digest_reject_without_partial_rows(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    bad_version = replace(graph.request.candidates[0], candidate_asset_version_id=uuid4())
    with pytest.raises(MusicDirectorPersistenceError) as missing:
        service.persist(
            replace(graph.request, candidates=(bad_version, graph.request.candidates[1]))
        )
    assert missing.value.code is MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
    bad_digest = replace(graph.request.candidates[0], proposal_digest="f" * 64)
    with pytest.raises(MusicDirectorPersistenceError) as digest:
        service.persist(
            replace(graph.request, candidates=(bad_digest, graph.request.candidates[1]))
        )
    assert digest.value.code is MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
    assert graph.count(MusicDirectorRun) == graph.count(MusicDirectorCandidate) == 0


def test_wrong_job_type_and_state_reject(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    with graph.factory() as session, session.begin():
        session.get(Job, graph.request.job_id).job_type = "export"
    with pytest.raises(MusicDirectorPersistenceError) as wrong_type:
        service.persist(graph.request)
    assert wrong_type.value.code is MusicDirectorPersistenceErrorCode.CONFLICT
    with graph.factory() as session, session.begin():
        job = session.get(Job, graph.request.job_id)
        job.job_type = "music_director"
        job.status = JobStatus.QUEUED
    with pytest.raises(MusicDirectorPersistenceError) as wrong_state:
        service.persist(graph.request)
    assert wrong_state.value.code is MusicDirectorPersistenceErrorCode.STALE_CLAIM
    assert graph.count(MusicDirectorRun) == 0


def test_candidate_insert_failure_rolls_back_run(graph, monkeypatch):
    from backend.repositories.workspace.music_director_repository import MusicDirectorRepository

    def fail(self, candidates):
        self._session.add(candidates[0])
        self._session.flush()
        raise RuntimeError("injected")

    monkeypatch.setattr(MusicDirectorRepository, "add_candidates", fail)
    with pytest.raises(RuntimeError, match="injected"):
        MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    assert graph.count(MusicDirectorRun) == graph.count(MusicDirectorCandidate) == 0


def test_concurrent_mismatched_persistence_has_one_authority(graph):
    changed = replace(
        graph.request,
        candidates=(
            replace(graph.request.candidates[0], model="v2"),
            graph.request.candidates[1],
        ),
    )
    requests = (graph.request, changed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(MusicDirectorCandidatePersistenceService(graph.factory).persist, request)
            for request in requests
        ]
    successes = [future.result() for future in futures if future.exception() is None]
    failures = [future.exception() for future in futures if future.exception() is not None]
    assert len(successes) == len(failures) == 1
    assert isinstance(failures[0], MusicDirectorPersistenceError)
    assert failures[0].code is MusicDirectorPersistenceErrorCode.CONFLICT
    assert graph.count(MusicDirectorRun) == 1
    assert graph.count(MusicDirectorCandidate) == 2


def test_conflicting_count_artifact_and_snapshot_replays(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    service.persist(graph.request)
    conflicts = (
        replace(graph.request, candidates=(graph.request.candidates[0],)),
        replace(
            graph.request,
            candidates=(
                replace(graph.request.candidates[0], proposal_artifact_id=uuid4()),
                graph.request.candidates[1],
            ),
        ),
        replace(graph.request, composition_snapshot_id=uuid4()),
    )
    for request in conflicts:
        with pytest.raises(MusicDirectorPersistenceError) as error:
            service.persist(request)
        assert error.value.code is MusicDirectorPersistenceErrorCode.CONFLICT
    assert graph.count(MusicDirectorCandidate) == 2


def test_invalid_preview_binding_is_rejected(graph):
    invalid_preview = replace(
        graph.request.candidates[0],
        preview_artifact_id=graph.request.candidates[0].proposal_artifact_id,
    )
    with pytest.raises(MusicDirectorPersistenceError) as error:
        MusicDirectorCandidatePersistenceService(graph.factory).persist(
            replace(
                graph.request,
                candidates=(invalid_preview, graph.request.candidates[1]),
            )
        )
    assert error.value.code is MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
    assert graph.count(MusicDirectorRun) == 0


def test_cross_project_and_cross_run_selection_are_rejected(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    persisted = service.persist(graph.request)
    with pytest.raises(MusicDirectorPersistenceError) as project_error:
        service.select(
            project_id=uuid4(),
            run_id=persisted.run.run_id,
            candidate_id=persisted.candidates[0].candidate_id,
            expected_version=0,
        )
    assert project_error.value.code is MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
    with graph.factory() as session, session.begin():
        second_job = Job(
            project_id=graph.request.project_id,
            workspace_id=session.get(Job, graph.request.job_id).workspace_id,
            composition_snapshot_id=graph.request.composition_snapshot_id,
            job_type="music_director",
            status=JobStatus.RUNNING,
            api_contract_version="1",
            settings_snapshot={"music_intent": {"instruction": "other", "candidate_count": 1}},
            requested_by=graph.owner,
            claimed_by="worker",
            claim_token=uuid4(),
            lease_expires_at=datetime.now(UTC) + timedelta(hours=1),
            attempt=1,
        )
        session.add(second_job)
        session.flush()
        second_run = MusicDirectorRun(
            job_id=second_job.job_id,
            project_id=graph.request.project_id,
            composition_snapshot_id=graph.request.composition_snapshot_id,
        )
        session.add(second_run)
        session.flush()
        fact = graph.request.candidates[0]
        second_candidate = MusicDirectorCandidate(
            run_id=second_run.run_id,
            ordinal=0,
            status="generated",
            proposal_digest=fact.proposal_digest,
            candidate_asset_version_id=fact.candidate_asset_version_id,
            proposal_artifact_id=fact.proposal_artifact_id,
        )
        session.add(second_candidate)
        session.flush()
        second_candidate_id = second_candidate.candidate_id
    with pytest.raises(MusicDirectorPersistenceError) as run_error:
        service.select(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=second_candidate_id,
            expected_version=0,
        )
    assert run_error.value.code is MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
    assert graph.revision() == 7


def test_applied_candidate_cannot_be_rejected(graph):
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    persisted = service.persist(graph.request)
    candidate_id = persisted.candidates[0].candidate_id
    with graph.factory() as session, session.begin():
        candidate = session.get(MusicDirectorCandidate, candidate_id)
        candidate.status = "applied"
        run = session.get(MusicDirectorRun, persisted.run.run_id)
        run.applied_candidate_id = candidate_id
    with pytest.raises(MusicDirectorPersistenceError) as error:
        service.reject(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=candidate_id,
        )
    assert error.value.code is MusicDirectorPersistenceErrorCode.INVALID_TRANSITION


def test_run_and_selection_failure_injection_roll_back(graph, monkeypatch):
    from backend.repositories.workspace.music_director_repository import MusicDirectorRepository

    original_add_run = MusicDirectorRepository.add_run

    def fail_run(self, run):
        original_add_run(self, run)
        raise RuntimeError("run failure")

    monkeypatch.setattr(MusicDirectorRepository, "add_run", fail_run)
    with pytest.raises(RuntimeError, match="run failure"):
        MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    assert graph.count(MusicDirectorRun) == 0
    monkeypatch.setattr(MusicDirectorRepository, "add_run", original_add_run)
    service = MusicDirectorCandidatePersistenceService(graph.factory)
    persisted = service.persist(graph.request)
    original_select = MusicDirectorRepository.select_candidate

    def fail_selection(self, **kwargs):
        assert original_select(self, **kwargs)
        raise RuntimeError("selection failure")

    monkeypatch.setattr(MusicDirectorRepository, "select_candidate", fail_selection)
    with pytest.raises(RuntimeError, match="selection failure"):
        service.select(
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
            candidate_id=persisted.candidates[0].candidate_id,
            expected_version=0,
        )
    with graph.factory() as session:
        run = session.get(MusicDirectorRun, persisted.run.run_id)
        assert run.selected_candidate_id is None
        assert run.version == 0
