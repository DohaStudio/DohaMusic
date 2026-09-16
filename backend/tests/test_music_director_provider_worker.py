from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.contracts.music_director import MusicIntent
from backend.contracts.music_director_provider import MusicDirectorProviderRequest
from backend.models.workspace import Job, JobStatus, MusicDirectorCandidate
from backend.models.workspace.provider_execution import MusicDirectorProviderExecution
from backend.providers.music_director_mock import (
    MockMusicDirectorProvider,
    MockMusicDirectorProviderError,
)
from backend.services.workspace.music_director_worker_service import (
    MusicDirectorWorkerError,
    MusicDirectorWorkerService,
)
from backend.services.workspace.provider_execution_service import (
    MusicDirectorProviderExecutionService,
)
from backend.tests.test_music_director_materialization_service import _service


def test_mock_provider_is_deterministic_and_rejects_same_key_conflict():
    provider = MockMusicDirectorProvider()
    request = MusicDirectorProviderRequest(
        "a" * 64, __import__("uuid").uuid4(), MusicIntent("variation", 2), "mock-v1"
    )
    first = provider.submit(request)
    assert provider.submit(request) == first
    assert provider.remote_execution_count == 1
    with pytest.raises(MockMusicDirectorProviderError):
        provider.submit(replace(request, intent=MusicIntent("different", 2)))


@pytest.mark.parametrize("count", [1, 2, 4])
def test_worker_materializes_candidate_set_and_terminal_replay_is_remote_free(tmp_path, count):
    graph, materialization, request, _, _ = _service(tmp_path, count)
    with graph.factory() as session, session.begin():
        job = session.get(Job, request.job_id)
        job.provider_id = "mock-music-director"
        job.model_manifest_id = "mock-v1"
        job.settings_snapshot = {
            "music_intent": {"instruction": "variation", "candidate_count": count}
        }
    provider = MockMusicDirectorProvider()
    worker = MusicDirectorWorkerService(
        graph.factory,
        provider=provider,
        provider_executions=MusicDirectorProviderExecutionService(graph.factory),
        materialization=materialization,
    )
    result = worker.execute_owned_claim(
        job_id=request.job_id,
        claimed_by=request.claimed_by,
        claim_token=request.claim_token,
    )
    assert len(result.candidates) == count
    assert provider.remote_execution_count == 1
    submit_calls, read_calls = provider.submit_calls, provider.read_calls
    replay = worker.execute_owned_claim(
        job_id=request.job_id,
        claimed_by=request.claimed_by,
        claim_token=request.claim_token,
    )
    assert tuple(item.candidate_id for item in replay.candidates) == tuple(
        item.candidate_id for item in result.candidates
    )
    assert (provider.submit_calls, provider.read_calls) == (submit_calls, read_calls)
    with graph.factory() as session:
        assert session.get(Job, request.job_id).status is JobStatus.SUCCEEDED
        assert session.scalar(select(func.count()).select_from(MusicDirectorProviderExecution)) == 1
        assert session.scalar(select(func.count()).select_from(MusicDirectorCandidate)) == count
    graph.engine.dispose()


@pytest.mark.parametrize("mode", ["failed", "wrong_count", "duplicate_ordinal", "invalid_proposal"])
def test_worker_fails_closed_without_partial_candidates(tmp_path, mode):
    graph, materialization, request, _, _ = _service(tmp_path, 2)
    with graph.factory() as session, session.begin():
        job = session.get(Job, request.job_id)
        job.provider_id = "mock-music-director"
        job.settings_snapshot = {"music_intent": {"instruction": "variation", "candidate_count": 2}}
    worker = MusicDirectorWorkerService(
        graph.factory,
        provider=MockMusicDirectorProvider(mode=mode),
        provider_executions=MusicDirectorProviderExecutionService(graph.factory),
        materialization=materialization,
    )
    with pytest.raises(MusicDirectorWorkerError):
        worker.execute_owned_claim(
            job_id=request.job_id,
            claimed_by=request.claimed_by,
            claim_token=request.claim_token,
        )
    with graph.factory() as session:
        assert session.get(Job, request.job_id).status is JobStatus.FAILED
        assert session.scalar(select(func.count()).select_from(MusicDirectorCandidate)) == 0
    graph.engine.dispose()


def test_pre_submit_cancellation_is_terminal_and_idempotent(tmp_path):
    graph, materialization, request, _, _ = _service(tmp_path, 2)
    with graph.factory() as session, session.begin():
        job = session.get(Job, request.job_id)
        job.cancel_requested_at = datetime.now(UTC)
    provider = MockMusicDirectorProvider()
    worker = MusicDirectorWorkerService(
        graph.factory,
        provider=provider,
        provider_executions=MusicDirectorProviderExecutionService(graph.factory),
        materialization=materialization,
    )
    for _ in range(2):
        with pytest.raises(MusicDirectorWorkerError) as error:
            worker.execute_owned_claim(
                job_id=request.job_id,
                claimed_by=request.claimed_by,
                claim_token=request.claim_token,
            )
        assert error.value.code.value == "MUSIC_DIRECTOR_CANCELLED"
    with graph.factory() as session:
        assert session.get(Job, request.job_id).status is JobStatus.CANCELLED
        assert session.scalar(select(func.count()).select_from(MusicDirectorProviderExecution)) == 0
        assert session.scalar(select(func.count()).select_from(MusicDirectorCandidate)) == 0
    assert provider.submit_calls == 0
    assert provider.read_calls == 0
    graph.engine.dispose()


def test_pre_submit_cancellation_rejects_stale_token_without_overwrite(tmp_path):
    graph, materialization, request, _, _ = _service(tmp_path, 1)
    with graph.factory() as session, session.begin():
        session.get(Job, request.job_id).cancel_requested_at = datetime.now(UTC)
    worker = MusicDirectorWorkerService(
        graph.factory,
        provider=MockMusicDirectorProvider(),
        provider_executions=MusicDirectorProviderExecutionService(graph.factory),
        materialization=materialization,
    )
    with pytest.raises(MusicDirectorWorkerError) as error:
        worker.execute_owned_claim(
            job_id=request.job_id,
            claimed_by=request.claimed_by,
            claim_token=uuid4(),
        )
    assert error.value.code.value == "MUSIC_DIRECTOR_STALE_CLAIM"
    with graph.factory() as session:
        assert session.get(Job, request.job_id).status is JobStatus.RUNNING
    graph.engine.dispose()
