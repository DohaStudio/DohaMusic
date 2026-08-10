"""Workspace Job의 claim·lease·Provider dispatch 실행 경계."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace import Job, JobStatus, Workspace
from backend.repositories.workspace import JobRepository
from backend.services.workspace.job_completion_service import (
    JobCompletionService,
    ProviderResult,
)
from backend.services.workspace.job_service import BYTE_INPUT_ROLES

DEFAULT_LEASE_DURATION = timedelta(minutes=5)
MIN_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 3600
MAX_WORKER_ID_LENGTH = 128


class ProviderDispatchStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class ProviderExecutionInput:
    input_order: int
    input_role: str
    artifact_id: UUID | None
    asset_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class ProviderExecutionRequest:
    job_id: UUID
    capability: str
    provider_id: str | None
    provider_contract_version: str
    model_manifest_id: str | None
    idempotency_key: str
    inputs: tuple[ProviderExecutionInput, ...]
    settings: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProviderDispatchResult:
    status: ProviderDispatchStatus
    provider_result: ProviderResult | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False


class ProviderExecutionContext:
    """느린 dispatch가 lease를 연장하고 cancel marker를 확인하는 내부 경계."""

    def __init__(
        self,
        heartbeat: Callable[[], None],
        cancellation_requested: Callable[[], bool],
    ) -> None:
        self._heartbeat = heartbeat
        self._cancellation_requested = cancellation_requested

    def heartbeat(self) -> None:
        self._heartbeat()

    def cancellation_requested(self) -> bool:
        return self._cancellation_requested()


class ProviderDispatcher(Protocol):
    def execute(
        self,
        request: ProviderExecutionRequest,
        context: ProviderExecutionContext,
    ) -> ProviderDispatchResult: ...


class JobWorkerError(RuntimeError):
    pass


class JobWorkerService:
    """짧은 DB transaction 사이에서 단일 Worker iteration을 실행한다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        worker_id: str,
        dispatcher: ProviderDispatcher,
        completion_service: JobCompletionService,
        lease_duration: timedelta = DEFAULT_LEASE_DURATION,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if (
            type(worker_id) is not str
            or not worker_id.strip()
            or len(worker_id) > MAX_WORKER_ID_LENGTH
            or any(ord(char) < 33 or char in "\\/" for char in worker_id)
        ):
            raise ValueError("worker_id must be a bounded opaque identifier")
        seconds = lease_duration.total_seconds()
        if seconds < MIN_LEASE_SECONDS or seconds > MAX_LEASE_SECONDS:
            raise ValueError("lease duration is outside the safe range")
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._dispatcher = dispatcher
        self._completion = completion_service
        self._lease_duration = lease_duration
        self._clock = clock

    def claim_one(self) -> Job | None:
        now = self._clock()
        with self._session_factory() as session, session.begin():
            return JobRepository(session).claim_next_job(
                claimed_by=self._worker_id,
                claim_token=uuid4(),
                now=now,
                lease_expires_at=now + self._lease_duration,
            )

    def heartbeat(self, job_id: UUID, claim_token: UUID) -> Job:
        now = self._clock()
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).heartbeat_claim(
                job_id,
                claimed_by=self._worker_id,
                claim_token=claim_token,
                now=now,
                lease_expires_at=now + self._lease_duration,
            )
            if job is None:
                raise JobWorkerError("Workspace Job heartbeat ownership is invalid.")
            return job

    def recover_one_expired(self) -> Job | None:
        with self._session_factory() as session, session.begin():
            return JobRepository(session).recover_expired_claim(now=self._clock())

    def run_once(self) -> Job | None:
        job = self.claim_one()
        if job is None:
            return None
        if job.claim_token is None:
            raise JobWorkerError("Workspace Job claim token is missing.")
        token = job.claim_token
        try:
            request, owner_id = self._execution_request(job.job_id, token)
        except JobWorkerError:
            return self._fail(job.job_id, token, "PROVIDER_REQUEST_INVALID", False)
        if self._cancel_requested(job.job_id, token):
            return self._finish(job.job_id, token, JobStatus.CANCELLED)
        context = ProviderExecutionContext(
            lambda: self.heartbeat(job.job_id, token),
            lambda: self._cancel_requested(job.job_id, token),
        )
        try:
            result = self._dispatcher.execute(request, context)
        except TimeoutError:
            if self._cancel_requested(job.job_id, token):
                return self._finish(job.job_id, token, JobStatus.CANCELLED)
            return self._fail(job.job_id, token, "PROVIDER_TIMEOUT", True)
        except Exception:
            if self._cancel_requested(job.job_id, token):
                return self._finish(job.job_id, token, JobStatus.CANCELLED)
            return self._fail(job.job_id, token, "PROVIDER_EXECUTION_FAILED", True)
        if (
            self._cancel_requested(job.job_id, token)
            or result.status is ProviderDispatchStatus.CANCELLED
        ):
            return self._finish(job.job_id, token, JobStatus.CANCELLED)
        if result.status is ProviderDispatchStatus.TIMED_OUT:
            return self._fail(job.job_id, token, "PROVIDER_TIMEOUT", True)
        if result.status is ProviderDispatchStatus.FAILED:
            return self._fail(
                job.job_id,
                token,
                result.error_code or "PROVIDER_EXECUTION_FAILED",
                result.retryable,
            )
        if (
            result.status is not ProviderDispatchStatus.SUCCEEDED
            or result.provider_result is None
        ):
            return self._fail(job.job_id, token, "PROVIDER_RESULT_INVALID", False)
        try:
            completed = self._completion.complete_job_with_provider_result(
                job.job_id,
                effective_owner_id=owner_id,
                provider_result=result.provider_result,
                execution_claim_token=token,
            )
        except Exception:
            with self._session_factory() as session:
                current = JobRepository(session).get_job(job.job_id)
                if current is not None and current.status is not JobStatus.RUNNING:
                    return current
            return self._fail(job.job_id, token, "PROVIDER_RESULT_INVALID", False)
        return completed.aggregate.job

    def _execution_request(
        self, job_id: UUID, claim_token: UUID
    ) -> tuple[ProviderExecutionRequest, UUID]:
        with self._session_factory() as session:
            repository = JobRepository(session)
            job = repository.get_job(job_id)
            if (
                job is None
                or job.status is not JobStatus.RUNNING
                or job.claim_token != claim_token
                or job.claimed_by != self._worker_id
            ):
                raise JobWorkerError("Workspace Job claim ownership is invalid.")
            owner_id = session.scalar(
                select(Workspace.owner_id).where(
                    Workspace.workspace_id == job.workspace_id,
                    Workspace.deleted_at.is_(None),
                )
            )
            if owner_id is None:
                raise JobWorkerError("Workspace Job owner scope is invalid.")
            inputs = []
            for item in repository.list_job_inputs(job_id):
                role = item.input_role or ""
                if role in BYTE_INPUT_ROLES and item.artifact_id is None:
                    raise JobWorkerError("Byte-level Job input requires an Artifact.")
                inputs.append(
                    ProviderExecutionInput(
                        item.input_order,
                        role,
                        item.artifact_id,
                        item.asset_version_id,
                    )
                )
            return (
                ProviderExecutionRequest(
                    job_id=job.job_id,
                    capability=job.job_type,
                    provider_id=job.provider_id,
                    provider_contract_version=job.api_contract_version,
                    model_manifest_id=job.model_manifest_id,
                    idempotency_key=f"workspace-job:{job.job_id}",
                    inputs=tuple(inputs),
                    settings=dict(job.settings_snapshot),
                ),
                owner_id,
            )

    def _cancel_requested(self, job_id: UUID, token: UUID) -> bool:
        with self._session_factory() as session:
            job = JobRepository(session).get_job(job_id)
            return bool(
                job
                and job.status is JobStatus.RUNNING
                and job.claim_token == token
                and job.claimed_by == self._worker_id
                and job.cancel_requested_at is not None
            )

    def _finish(self, job_id: UUID, token: UUID, status: JobStatus) -> Job:
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).finish_owned_claim(
                job_id,
                claimed_by=self._worker_id,
                claim_token=token,
                status=status,
                now=self._clock(),
            )
            if job is None:
                raise JobWorkerError("Workspace Job terminal ownership is invalid.")
            return job

    def _fail(self, job_id: UUID, token: UUID, code: str, retryable: bool) -> Job:
        safe_code = (
            code if code.isupper() and len(code) <= 64 else "PROVIDER_EXECUTION_FAILED"
        )
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).finish_owned_claim(
                job_id,
                claimed_by=self._worker_id,
                claim_token=token,
                status=JobStatus.FAILED,
                now=self._clock(),
                error_code=safe_code,
                error_message="Workspace Job provider execution failed.",
                error_retryable=retryable,
            )
            if job is None:
                raise JobWorkerError("Workspace Job failure ownership is invalid.")
            return job
