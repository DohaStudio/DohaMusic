from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.api.v1.routes.music_director import _map_error
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.workspace import (
    Job,
    JobStatus,
    MusicDirectorCandidate,
    MusicDirectorRun,
    WorkingComposition,
    WorkingCompositionHistoryEntry,
)
from backend.repositories.idempotency_repository import IdempotencyRepository
from backend.repositories.workspace.music_director_repository import MusicDirectorRepository
from backend.services.workspace.music_director_apply_service import (
    MUSIC_DIRECTOR_APPLY_CONTRACT_VERSION,
    MusicDirectorApplyError,
    MusicDirectorApplyErrorCode,
    MusicDirectorApplyService,
)
from backend.services.workspace.music_director_candidate_persistence_service import (
    MusicDirectorCandidatePersistenceService,
)
from backend.services.workspace.working_composition_service import WorkingCompositionService
from backend.tests.test_music_director_materialization_service import _service

_GRAPHS = []


@pytest.fixture(autouse=True)
def _dispose_graphs():
    yield
    while _GRAPHS:
        _GRAPHS.pop().engine.dispose()


def _ready(tmp_path, *, count=1):
    graph, materializer, request, roots, _ = _service(tmp_path, count)
    _GRAPHS.append(graph)
    result = materializer.materialize(request)
    candidate = result.candidates[0]
    with graph.factory() as session, session.begin():
        session.get(Job, graph.request.job_id).status = JobStatus.SUCCEEDED
    selected = MusicDirectorCandidatePersistenceService(graph.factory).select(
        project_id=graph.request.project_id,
        run_id=result.run.run_id,
        candidate_id=candidate.candidate_id,
        expected_version=0,
    )
    service = MusicDirectorApplyService(graph.factory, artifact_roots=roots)
    return graph, service, selected, candidate, roots


def _apply(graph, service, run, candidate, *, key="apply-1", run_version=None, revision=7):
    return service.apply(
        effective_owner_id=graph.owner,
        project_id=graph.request.project_id,
        run_id=run.run_id,
        candidate_id=candidate.candidate_id,
        expected_run_version=run.version if run_version is None else run_version,
        expected_working_composition_revision=revision,
        idempotency_key=key,
    )


def test_apply_is_atomic_and_exact_replay_is_idempotent(tmp_path) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path)

    first = _apply(graph, service, run, candidate)
    replay = _apply(graph, service, run, candidate)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.history_entry_id == first.history_entry_id
    assert replay.working_composition_revision == first.working_composition_revision == 8
    with graph.factory() as session:
        current_run = session.get(MusicDirectorRun, run.run_id)
        current_candidate = session.get(MusicDirectorCandidate, candidate.candidate_id)
        working = session.get(WorkingComposition, graph.working_id)
        history_count = session.scalar(
            select(func.count()).select_from(WorkingCompositionHistoryEntry)
        )
        assert current_run.applied_candidate_id == candidate.candidate_id
        assert current_run.applied_working_revision == 8
        assert current_run.version == 2
        assert current_candidate.status == "applied"
        assert working.revision == 8
        assert str(working.master_gain_db) == "-1.0000"
        assert history_count == 1


def test_apply_is_one_aggregate_undo_redo_command(tmp_path) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path)
    applied = _apply(graph, service, run, candidate)
    working_service = WorkingCompositionService(graph.factory)

    undone = working_service.undo_history(
        graph.request.project_id,
        working_composition_id=graph.working_id,
        expected_revision=applied.working_composition_revision,
        effective_owner_id=graph.owner,
        idempotency_key="undo-apply",
    )
    with graph.factory() as session:
        working = session.get(WorkingComposition, graph.working_id)
        assert str(working.master_gain_db) == "0.0000"
        assert working.revision == undone.completed_revision == 9

    redone = working_service.redo_history(
        graph.request.project_id,
        working_composition_id=graph.working_id,
        expected_revision=undone.completed_revision,
        effective_owner_id=graph.owner,
        idempotency_key="redo-apply",
    )
    with graph.factory() as session:
        working = session.get(WorkingComposition, graph.working_id)
        assert str(working.master_gain_db) == "-1.0000"
        assert working.revision == redone.completed_revision == 10
        assert session.get(MusicDirectorRun, run.run_id).applied_candidate_id == (
            candidate.candidate_id
        )


@pytest.mark.parametrize(
    ("run_version", "revision", "code"),
    [
        (0, 7, MusicDirectorApplyErrorCode.STALE_RUN),
        (1, 6, MusicDirectorApplyErrorCode.STALE_WORKING_COMPOSITION),
    ],
)
def test_apply_rejects_stale_double_cas_without_partial_mutation(
    tmp_path, run_version, revision, code
) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path)

    with pytest.raises(MusicDirectorApplyError) as error:
        _apply(
            graph,
            service,
            run,
            candidate,
            run_version=run_version,
            revision=revision,
        )

    assert error.value.code is code
    assert graph.revision() == 7
    with graph.factory() as session:
        assert session.get(MusicDirectorRun, run.run_id).applied_candidate_id is None
        assert session.get(MusicDirectorCandidate, candidate.candidate_id).status == "generated"
        assert session.scalar(select(func.count()).select_from(WorkingCompositionHistoryEntry)) == 0


def test_apply_rejects_tampered_proposal_without_partial_mutation(tmp_path) -> None:
    graph, service, run, candidate, roots = _ready(tmp_path)
    with graph.factory() as session:
        materialization = MusicDirectorRepository(session).list_materializations(
            graph.request.job_id
        )[0]
    path = roots.candidate_path(materialization.storage_domain, materialization.storage_key)
    Path(path).write_bytes(b'{"tampered":true}')

    with pytest.raises(MusicDirectorApplyError) as error:
        _apply(graph, service, run, candidate)

    assert error.value.code is MusicDirectorApplyErrorCode.ARTIFACT_MISMATCH
    assert graph.revision() == 7
    with graph.factory() as session:
        assert session.get(MusicDirectorRun, run.run_id).applied_candidate_id is None
        assert session.scalar(select(func.count()).select_from(WorkingCompositionHistoryEntry)) == 0


def test_apply_requires_complete_whole_set(tmp_path) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path, count=2)
    with graph.factory() as session, session.begin():
        materials = MusicDirectorRepository(session).list_materializations(graph.request.job_id)
        materials[1].status = "published"

    with pytest.raises(MusicDirectorApplyError) as error:
        _apply(graph, service, run, candidate)

    assert error.value.code is MusicDirectorApplyErrorCode.NOT_READY
    assert graph.revision() == 7


def _fingerprint_values(graph, run, candidate):
    return {
        "effective_owner_id": graph.owner,
        "project_id": graph.request.project_id,
        "run_id": run.run_id,
        "candidate_id": candidate.candidate_id,
        "working_composition_id": graph.working_id,
        "expected_run_version": run.version,
        "expected_working_composition_revision": 7,
        "proposal_artifact_id": candidate.proposal_artifact_id,
        "apply_contract_version": MUSIC_DIRECTOR_APPLY_CONTRACT_VERSION,
        "proposal_schema_version": 1,
        "proposal_digest": candidate.proposal_digest,
    }


@pytest.mark.parametrize("field", ["proposal_artifact_id", "apply_contract_version"])
def test_apply_fingerprint_binds_artifact_and_contract_version(field) -> None:
    values = {"proposal_artifact_id": uuid4(), "apply_contract_version": 1}
    first = MusicDirectorApplyService._fingerprint(**values)
    assert MusicDirectorApplyService._fingerprint(**dict(reversed(list(values.items())))) == first
    values[field] = uuid4() if field == "proposal_artifact_id" else 2
    assert MusicDirectorApplyService._fingerprint(**values) != first


def test_apply_different_fingerprint_conflicts_without_second_mutation(tmp_path) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path)
    expected = service._fingerprint(**_fingerprint_values(graph, run, candidate))
    first = _apply(graph, service, run, candidate)
    with graph.factory() as session:
        record = session.scalar(select(IdempotencyRecord))
        completion = dict(record.result_payload)
        assert record.request_fingerprint == expected
    with pytest.raises(MusicDirectorApplyError) as error:
        _apply(graph, service, run, candidate, revision=8)
    assert error.value.code is MusicDirectorApplyErrorCode.IDEMPOTENCY_CONFLICT
    assert str(error.value.__cause__) == "IDEMPOTENCY_CONFLICT"
    assert _map_error(error.value).code == "MUSIC_DIRECTOR_APPLY_IDEMPOTENCY_CONFLICT"
    with graph.factory() as session:
        working = session.get(WorkingComposition, graph.working_id)
        current = session.get(MusicDirectorRun, run.run_id)
        record = session.scalar(select(IdempotencyRecord))
        assert working.revision == first.working_composition_revision == 8
        assert str(working.master_gain_db) == "-1.0000"
        assert current.version == 2
        assert (
            current.selected_candidate_id == current.applied_candidate_id == candidate.candidate_id
        )
        assert current.applied_working_revision == 8
        assert session.get(MusicDirectorCandidate, candidate.candidate_id).status == "applied"
        assert session.scalar(select(func.count()).select_from(WorkingCompositionHistoryEntry)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
        assert record.status == "COMPLETED"
        assert record.completed_revision == 8
        assert record.result_payload == completion
        assert record.request_fingerprint == expected


def test_apply_in_progress_is_not_stale_run(tmp_path) -> None:
    graph, service, run, candidate, _ = _ready(tmp_path)
    with graph.factory() as session, session.begin():
        IdempotencyRepository(session).claim_with_result(
            scope=f"music-director-apply:{graph.request.project_id}",
            key="apply-1",
            fingerprint=service._fingerprint(**_fingerprint_values(graph, run, candidate)),
            now=datetime.now(UTC),
        )
    with pytest.raises(MusicDirectorApplyError) as error:
        _apply(graph, service, run, candidate)
    assert error.value.code is MusicDirectorApplyErrorCode.IDEMPOTENCY_IN_PROGRESS
    assert str(error.value.__cause__) == "IDEMPOTENCY_IN_PROGRESS"
    assert _map_error(error.value).code == "MUSIC_DIRECTOR_APPLY_IDEMPOTENCY_IN_PROGRESS"
    assert graph.revision() == 7
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(WorkingCompositionHistoryEntry)) == 0
        assert session.get(MusicDirectorRun, run.run_id).applied_candidate_id is None
        assert session.get(MusicDirectorCandidate, candidate.candidate_id).status == "generated"
        assert session.scalar(select(IdempotencyRecord)).status == "IN_PROGRESS"
