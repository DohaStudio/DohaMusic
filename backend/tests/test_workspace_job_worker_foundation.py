"""Workspace Job Worker claim·lease·dispatch 경계 검증."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    AssetType,
    AssetVersion,
    Job,
    JobOutput,
    JobStatus,
    ModelUsage,
)
from backend.repositories.workspace import JobRepository
from backend.services.workspace import (
    ArtifactIngestionService,
    AssetService,
    JobCompletionService,
    JobService,
    JobWorkerError,
    JobWorkerService,
    ProviderDispatchResult,
    ProviderDispatchStatus,
    ProviderOutput,
    ProviderResult,
    ProviderResultStatus,
    WorkspaceService,
)
from backend.storage.artifact_resolver import ArtifactStorageRoots


class FakeDispatcher:
    def __init__(self, result=None, hook=None) -> None:
        self.result = result
        self.hook = hook
        self.requests = []

    def execute(self, request, context):
        self.requests.append(request)
        if self.hook:
            self.hook(context)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result or ProviderDispatchResult(ProviderDispatchStatus.MALFORMED)


class RetryingFakeDispatcher:
    """동일 요청을 transport retry로 두 번 전송하고 첫 결과를 반환한다."""

    def __init__(self, first, replay) -> None:
        self.first = first
        self.replay = replay
        self.requests = []
        self.replay_result = None

    def _send(self, request, result):
        self.requests.append(request)
        return result

    def execute(self, request, context):
        first = self._send(request, self.first)
        replay = self._send(request, self.replay)
        self.replay_result = replay.provider_result
        return first


class WorkerFixture:
    def __init__(self, tmp_path: Path) -> None:
        self.now = datetime(2026, 8, 11, tzinfo=UTC)
        self.engine = create_database_engine(f"sqlite:///{tmp_path / 'worker.db'}")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.owner = uuid4()
        workspace = WorkspaceService(self.factory)
        self.workspace = workspace.create_workspace(owner_id=self.owner, name="Worker")
        self.project = workspace.create_project(
            workspace_id=self.workspace.workspace_id,
            title="Worker Project",
            created_by=self.owner,
        )
        artifact_root = tmp_path / "artifacts"
        for domain in ("lm", "audio", "vocal", "music"):
            (artifact_root / domain).mkdir(parents=True)
        staging = tmp_path / "staging"
        staging.mkdir()
        self.staging = staging
        self.ingestion = ArtifactIngestionService(
            self.factory,
            artifact_roots=ArtifactStorageRoots.from_base_root(artifact_root),
            staging_root=staging,
        )
        self.completion = JobCompletionService(
            self.factory, ingestion_service=self.ingestion
        )

    def create_job(self, *, job_type="lyrics_generation") -> Job:
        return (
            JobService(self.factory)
            .create_job_for_owner(
                effective_owner_id=self.owner,
                project_id=self.project.project_id,
                job_type=job_type,
                api_contract_version="1",
                settings_snapshot={"seed": 7},
                idempotency_key=f"worker-{uuid4()}",
                provider_id="provider-test",
                model_manifest_id="manifest-1",
            )
            .aggregate.job
        )

    def worker(self, dispatcher, *, worker_id="worker-a", lease=timedelta(minutes=5)):
        return JobWorkerService(
            self.factory,
            worker_id=worker_id,
            dispatcher=dispatcher,
            completion_service=self.completion,
            lease_duration=lease,
            clock=lambda: self.now,
        )

    def create_output_asset(self):
        return AssetService(self.factory).create_asset(
            workspace_id=self.workspace.workspace_id,
            owner_id=self.owner,
            asset_type=AssetType.LYRICS,
        )

    def success(self, *, target_asset_id=None):
        target_asset_id = target_asset_id or self.create_output_asset().asset_id
        payload = self.staging / f"{uuid4()}.txt"
        payload.write_text("worker output", encoding="utf-8")
        return ProviderDispatchResult(
            ProviderDispatchStatus.SUCCEEDED,
            ProviderResult(
                status=ProviderResultStatus.SUCCEEDED,
                provider_id="provider-test",
                capability="lyrics_generation",
                provider_contract_version="1",
                model_manifest_id="manifest-1",
                model_id="model-test",
                model_version="1",
                license_status="reviewed",
                commercial_usage_status="allowed",
                outputs=(
                    ProviderOutput(
                        0, "lyrics", payload, "lyrics_text", target_asset_id
                    ),
                ),
            ),
        )

    def persisted(self, job_id):
        with self.factory() as session:
            return session.get(Job, job_id)

    def output_count(self, job_id):
        with self.factory() as session:
            return len(JobRepository(session).list_job_outputs(job_id))

    def count(self, entity):
        with self.factory() as session:
            return session.scalar(select(func.count()).select_from(entity))


@pytest.fixture
def worker_fixture(tmp_path):
    fixture = WorkerFixture(tmp_path)
    yield fixture
    fixture.engine.dispose()


def test_no_job_is_a_noop(worker_fixture):
    assert worker_fixture.worker(FakeDispatcher()).run_once() is None


def test_claim_is_atomic_and_sets_execution_fields(worker_fixture):
    job = worker_fixture.create_job()
    claimed = worker_fixture.worker(FakeDispatcher()).claim_one()
    assert claimed.job_id == job.job_id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.claim_token and claimed.claimed_by == "worker-a"
    assert claimed.attempt == 1
    assert claimed.heartbeat_at == worker_fixture.now.replace(tzinfo=None)


def test_concurrent_claim_dispatches_once(worker_fixture):
    job = worker_fixture.create_job()
    barrier = __import__("threading").Barrier(2)

    def claim(name):
        barrier.wait()
        try:
            return worker_fixture.worker(FakeDispatcher(), worker_id=name).claim_one()
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("worker-a", "worker-b")))
    claimed = [item for item in results if item is not None]
    assert len(claimed) == 1 and claimed[0].job_id == job.job_id
    assert worker_fixture.persisted(job.job_id).attempt == 1


def test_cancel_marker_prevents_claim(worker_fixture):
    job = worker_fixture.create_job()
    with worker_fixture.factory() as session, session.begin():
        session.get(Job, job.job_id).cancel_requested_at = worker_fixture.now
    assert worker_fixture.worker(FakeDispatcher()).claim_one() is None


@pytest.mark.parametrize(
    "status",
    [JobStatus.RUNNING, JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED],
)
def test_non_queued_jobs_are_not_claimed(worker_fixture, status):
    job = worker_fixture.create_job()
    with worker_fixture.factory() as session, session.begin():
        session.get(Job, job.job_id).status = status
    assert worker_fixture.worker(FakeDispatcher()).claim_one() is None


def test_heartbeat_extends_lease_and_rejects_wrong_token(worker_fixture):
    worker_fixture.create_job()
    service = worker_fixture.worker(FakeDispatcher())
    claimed = service.claim_one()
    old_lease = claimed.lease_expires_at
    worker_fixture.now += timedelta(minutes=1)
    updated = service.heartbeat(claimed.job_id, claimed.claim_token)
    assert updated.lease_expires_at > old_lease
    with pytest.raises(JobWorkerError):
        service.heartbeat(claimed.job_id, uuid4())


def test_heartbeat_is_monotonic(worker_fixture):
    worker_fixture.create_job()
    service = worker_fixture.worker(FakeDispatcher())
    claimed = service.claim_one()
    worker_fixture.now -= timedelta(seconds=1)
    with pytest.raises(JobWorkerError):
        service.heartbeat(claimed.job_id, claimed.claim_token)


def test_expired_lease_becomes_retryable_failure(worker_fixture):
    worker_fixture.create_job()
    service = worker_fixture.worker(FakeDispatcher(), lease=timedelta(seconds=30))
    claimed = service.claim_one()
    worker_fixture.now += timedelta(seconds=31)
    recovered = service.recover_one_expired()
    assert recovered.job_id == claimed.job_id
    assert recovered.status is JobStatus.FAILED
    assert recovered.error_code == "WORKER_LEASE_EXPIRED" and recovered.error_retryable


def test_fresh_heartbeat_wins_over_stale_recovery(worker_fixture):
    worker_fixture.create_job()
    service = worker_fixture.worker(FakeDispatcher(), lease=timedelta(seconds=30))
    claimed = service.claim_one()
    worker_fixture.now += timedelta(seconds=20)
    service.heartbeat(claimed.job_id, claimed.claim_token)
    worker_fixture.now += timedelta(seconds=15)
    assert service.recover_one_expired() is None
    assert worker_fixture.persisted(claimed.job_id).status is JobStatus.RUNNING


def test_provider_success_calls_completion(worker_fixture):
    job = worker_fixture.create_job()
    dispatcher = FakeDispatcher(worker_fixture.success())
    completed = worker_fixture.worker(dispatcher).run_once()
    assert completed.status is JobStatus.SUCCEEDED
    assert len(dispatcher.requests) == 1
    assert dispatcher.requests[0].idempotency_key == f"workspace-job:{job.job_id}"


def test_duplicate_dispatch_reuses_key_and_completion_lineage(worker_fixture):
    job = worker_fixture.create_job()
    target = worker_fixture.create_output_asset()
    dispatcher = RetryingFakeDispatcher(
        worker_fixture.success(target_asset_id=target.asset_id),
        worker_fixture.success(target_asset_id=target.asset_id),
    )
    completed = worker_fixture.worker(dispatcher).run_once()
    assert completed.status is JobStatus.SUCCEEDED
    assert len(dispatcher.requests) == 2
    assert {request.idempotency_key for request in dispatcher.requests} == {
        f"workspace-job:{job.job_id}"
    }

    counts = tuple(
        worker_fixture.count(entity)
        for entity in (
            AssetVersion,
            Artifact,
            ArtifactStorageLocation,
            JobOutput,
            ModelUsage,
        )
    )
    replay = worker_fixture.completion.complete_job_with_provider_result(
        job.job_id,
        effective_owner_id=worker_fixture.owner,
        provider_result=dispatcher.replay_result,
        execution_claim_token=completed.claim_token,
    )
    assert replay.replayed is True
    assert counts == tuple(
        worker_fixture.count(entity)
        for entity in (
            AssetVersion,
            Artifact,
            ArtifactStorageLocation,
            JobOutput,
            ModelUsage,
        )
    )


@pytest.mark.parametrize(
    "code",
    [
        "PROVIDER_TIMEOUT",
        "WORKER_LEASE_EXPIRED",
        "PROVIDER_CANCELLED",
        "MODEL_2_UNAVAILABLE",
    ],
)
def test_safe_provider_error_codes_are_preserved(worker_fixture, code):
    worker_fixture.create_job()
    failed = worker_fixture.worker(
        FakeDispatcher(
            ProviderDispatchResult(
                ProviderDispatchStatus.FAILED,
                error_code=code,
            )
        )
    ).run_once()
    assert failed.error_code == code


@pytest.mark.parametrize(
    "code",
    [
        r"C:\SECRET",
        "API_KEY=SECRET",
        "provider_timeout",
        "PROVIDER-TIMEOUT",
        "PROVIDER TIMEOUT",
        "/path/SECRET",
        "TRACE:SECRET",
    ],
)
def test_unsafe_provider_error_codes_use_safe_fallback(worker_fixture, code):
    worker_fixture.create_job()
    failed = worker_fixture.worker(
        FakeDispatcher(
            ProviderDispatchResult(
                ProviderDispatchStatus.FAILED,
                error_code=code,
            )
        )
    ).run_once()
    assert failed.error_code == "PROVIDER_EXECUTION_FAILED"


@pytest.mark.parametrize(
    ("result", "code", "retryable"),
    [
        (
            ProviderDispatchResult(ProviderDispatchStatus.FAILED),
            "PROVIDER_EXECUTION_FAILED",
            False,
        ),
        (
            ProviderDispatchResult(ProviderDispatchStatus.TIMED_OUT),
            "PROVIDER_TIMEOUT",
            True,
        ),
        (
            ProviderDispatchResult(ProviderDispatchStatus.MALFORMED),
            "PROVIDER_RESULT_INVALID",
            False,
        ),
        (TimeoutError(), "PROVIDER_TIMEOUT", True),
    ],
)
def test_provider_failures_are_safe(worker_fixture, result, code, retryable):
    job = worker_fixture.create_job()
    failed = worker_fixture.worker(FakeDispatcher(result)).run_once()
    assert failed.status is JobStatus.FAILED
    assert failed.error_code == code and failed.error_retryable is retryable
    assert worker_fixture.output_count(job.job_id) == 0


def test_cooperative_cancel_skips_completion(worker_fixture):
    job = worker_fixture.create_job()

    def request_cancel(context):
        with worker_fixture.factory() as session, session.begin():
            session.get(Job, job.job_id).cancel_requested_at = worker_fixture.now
        assert context.cancellation_requested()

    dispatcher = FakeDispatcher(worker_fixture.success(), hook=request_cancel)
    cancelled = worker_fixture.worker(dispatcher).run_once()
    assert cancelled.status is JobStatus.CANCELLED
    assert worker_fixture.output_count(job.job_id) == 0


@pytest.mark.parametrize("with_marker", [False, True])
def test_provider_explicit_cancelled_skips_completion(worker_fixture, with_marker):
    job = worker_fixture.create_job()

    def request_cancel(context):
        if with_marker:
            with worker_fixture.factory() as session, session.begin():
                session.get(Job, job.job_id).cancel_requested_at = worker_fixture.now

    cancelled = worker_fixture.worker(
        FakeDispatcher(
            ProviderDispatchResult(ProviderDispatchStatus.CANCELLED),
            hook=request_cancel,
        )
    ).run_once()
    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.error_code is None
    assert cancelled.error_message is None
    assert cancelled.error_retryable is None
    assert worker_fixture.output_count(job.job_id) == 0
    assert worker_fixture.count(AssetVersion) == 0
    assert worker_fixture.count(Artifact) == 0
    assert worker_fixture.count(ModelUsage) == 0


def test_provider_can_heartbeat_during_execution(worker_fixture):
    job = worker_fixture.create_job()

    def heartbeat(context):
        worker_fixture.now += timedelta(minutes=1)
        context.heartbeat()

    completed = worker_fixture.worker(
        FakeDispatcher(worker_fixture.success(), heartbeat)
    ).run_once()
    assert completed.status is JobStatus.SUCCEEDED
    assert worker_fixture.persisted(
        job.job_id
    ).heartbeat_at == worker_fixture.now.replace(tzinfo=None)


def test_public_retry_job_enters_same_worker_queue(worker_fixture):
    original = worker_fixture.create_job()
    with worker_fixture.factory() as session, session.begin():
        row = session.get(Job, original.job_id)
        row.status = JobStatus.FAILED
        row.error_retryable = True
    retried = (
        JobService(worker_fixture.factory)
        .retry_job_for_owner(
            original.job_id,
            effective_owner_id=worker_fixture.owner,
            idempotency_key=f"retry-{uuid4()}",
        )
        .aggregate.job
    )
    completed = worker_fixture.worker(
        FakeDispatcher(worker_fixture.success())
    ).run_once()
    assert (
        completed.job_id == retried.job_id and completed.status is JobStatus.SUCCEEDED
    )
    assert worker_fixture.persisted(original.job_id).status is JobStatus.FAILED


def test_claim_and_recovery_query_plans_use_worker_indexes(worker_fixture):
    with worker_fixture.factory() as session:
        claim = session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT job_id FROM jobs WHERE status='queued' AND cancel_requested_at IS NULL ORDER BY created_at, job_id LIMIT 1"
            )
        ).all()
        recovery = session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT job_id FROM jobs WHERE status='running' AND lease_expires_at < '9999-01-01' ORDER BY lease_expires_at, job_id LIMIT 1"
            )
        ).all()
    claim_plan = " ".join(str(row) for row in claim)
    recovery_plan = " ".join(str(row) for row in recovery)
    assert "ix_jobs_claim_queue" in claim_plan and "TEMP B-TREE" not in claim_plan
    assert (
        "ix_jobs_lease_recovery" in recovery_plan and "TEMP B-TREE" not in recovery_plan
    )
    assert "SCAN jobs" not in claim_plan and "SCAN jobs" not in recovery_plan
