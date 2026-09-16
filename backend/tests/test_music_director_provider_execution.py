from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.workspace import Job, JobStatus, MusicProject, Workspace
from backend.models.workspace.provider_execution import MusicDirectorProviderExecution
from backend.services.workspace.provider_execution_service import (
    MusicDirectorProviderExecutionService,
    ProviderExecutionError,
    ProviderExecutionErrorCode,
)


@pytest.fixture
def graph(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'provider-execution.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    owner_id, worker, token = uuid4(), "worker-a", uuid4()
    with factory() as session, session.begin():
        workspace = Workspace(owner_id=owner_id, name="Workspace", lifecycle_status="active")
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="Project",
            lifecycle_status="active",
            created_by=owner_id,
        )
        session.add(project)
        session.flush()
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type="music_director",
            status=JobStatus.RUNNING,
            provider_id="mock-director",
            api_contract_version="1",
            settings_snapshot={},
            requested_by=owner_id,
            claimed_by=worker,
            claim_token=token,
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        session.add(job)
    return factory, job.job_id, worker, token


def test_intent_replay_bind_and_response_loss_converge(graph):
    factory, job_id, worker, token = graph
    service = MusicDirectorProviderExecutionService(factory)
    first = service.create_or_replay_intent(
        job_id=job_id,
        claimed_by=worker,
        claim_token=token,
        provider_id="mock-director",
        model_id="mock-v1",
    )
    fresh = MusicDirectorProviderExecutionService(factory)
    replay = fresh.create_or_replay_intent(
        job_id=job_id,
        claimed_by=worker,
        claim_token=token,
        provider_id="mock-director",
        model_id="mock-v1",
    )
    assert replay.provider_execution_id == first.provider_execution_id
    assert replay.client_execution_key == first.client_execution_key
    remote_executions: dict[str, str] = {}

    def submit(client_key: str) -> str:
        return remote_executions.setdefault(client_key, "remote-1")

    assert submit(first.client_execution_key) == "remote-1"
    assert submit(replay.client_execution_key) == "remote-1"
    assert len(remote_executions) == 1
    bound = fresh.bind_external_id(
        job_id=job_id, claimed_by=worker, claim_token=token, external_job_id="remote-1"
    )
    assert bound.external_job_id == "remote-1"
    assert (
        fresh.bind_external_id(
            job_id=job_id, claimed_by=worker, claim_token=token, external_job_id="remote-1"
        ).provider_execution_id
        == first.provider_execution_id
    )
    with factory() as session:
        assert len(session.scalars(select(MusicDirectorProviderExecution)).all()) == 1


def test_external_identity_mismatch_fails_closed(graph):
    factory, job_id, worker, token = graph
    service = MusicDirectorProviderExecutionService(factory)
    service.create_or_replay_intent(
        job_id=job_id,
        claimed_by=worker,
        claim_token=token,
        provider_id="mock-director",
        model_id=None,
    )
    service.bind_external_id(
        job_id=job_id, claimed_by=worker, claim_token=token, external_job_id="remote-1"
    )
    with pytest.raises(ProviderExecutionError) as error:
        service.bind_external_id(
            job_id=job_id, claimed_by=worker, claim_token=token, external_job_id="remote-2"
        )
    assert error.value.code is ProviderExecutionErrorCode.IDENTITY_MISMATCH

    with factory() as session, session.begin():
        source = session.get(Job, job_id)
        other = Job(
            project_id=source.project_id,
            workspace_id=source.workspace_id,
            job_type="music_director",
            status=JobStatus.RUNNING,
            provider_id="mock-director",
            api_contract_version="1",
            settings_snapshot={},
            requested_by=source.requested_by,
            claimed_by=worker,
            claim_token=token,
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        session.add(other)
        session.flush()
        other_id = other.job_id
    service.create_or_replay_intent(
        job_id=other_id,
        claimed_by=worker,
        claim_token=token,
        provider_id="mock-director",
        model_id=None,
    )
    with pytest.raises(ProviderExecutionError) as collision:
        service.bind_external_id(
            job_id=other_id,
            claimed_by=worker,
            claim_token=token,
            external_job_id="remote-1",
        )
    assert collision.value.code is ProviderExecutionErrorCode.IDENTITY_MISMATCH


def test_stale_claim_and_cancel_before_submit(graph):
    factory, job_id, worker, token = graph
    service = MusicDirectorProviderExecutionService(factory)
    with pytest.raises(ProviderExecutionError) as error:
        service.create_or_replay_intent(
            job_id=job_id,
            claimed_by=worker,
            claim_token=uuid4(),
            provider_id="mock-director",
            model_id=None,
        )
    assert error.value.code is ProviderExecutionErrorCode.STALE_CLAIM
    service.create_or_replay_intent(
        job_id=job_id,
        claimed_by=worker,
        claim_token=token,
        provider_id="mock-director",
        model_id=None,
    )
    with factory() as session, session.begin():
        session.get(Job, job_id).cancel_requested_at = datetime.now(UTC)
    cancelled = service.cancel_before_submit(job_id=job_id, claimed_by=worker, claim_token=token)
    assert cancelled.status == "cancelled"
