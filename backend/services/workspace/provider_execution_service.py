from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.models.workspace import JobStatus
from backend.models.workspace.provider_execution import (
    MusicDirectorProviderExecution,
    MusicDirectorProviderExecutionStatus,
)
from backend.repositories.workspace import JobRepository
from backend.repositories.workspace.provider_execution_repository import (
    MusicDirectorProviderExecutionRepository,
)

MUSIC_DIRECTOR_JOB_TYPE = "music_director"
_IDENTIFIER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?\Z")
_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "reconciliation_required"})


class ProviderExecutionErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    STALE_CLAIM = "STALE_CLAIM"
    CANCELLED = "CANCELLED"
    IDENTITY_MISMATCH = "PROVIDER_EXECUTION_IDENTITY_MISMATCH"
    INVALID_TRANSITION = "INVALID_TRANSITION"


class ProviderExecutionError(RuntimeError):
    def __init__(self, code: ProviderExecutionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class MusicDirectorProviderExecutionService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def create_or_replay_intent(
        self,
        *,
        job_id: UUID,
        claimed_by: str,
        claim_token: UUID,
        provider_id: str,
        model_id: str | None,
    ) -> MusicDirectorProviderExecution:
        provider = _identifier(provider_id, 128)
        model = _identifier(model_id, 256) if model_id is not None else None
        try:
            with self._session_factory() as session, session.begin():
                self._require_claim(session, job_id, claimed_by, claim_token)
                repository = MusicDirectorProviderExecutionRepository(session)
                existing = repository.get_for_job(job_id)
                if existing is not None:
                    self._require_exact(existing, provider, model)
                    return existing
                return repository.add(
                    MusicDirectorProviderExecution(
                        job_id=job_id,
                        provider_id=provider,
                        model_id=model,
                        client_execution_key=str(uuid4()),
                        status=MusicDirectorProviderExecutionStatus.INTENDED.value,
                    )
                )
        except IntegrityError:
            with self._session_factory() as session:
                existing = MusicDirectorProviderExecutionRepository(session).get_for_job(job_id)
                if existing is None:
                    raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT) from None
                self._require_exact(existing, provider, model)
                return existing

    def bind_external_id(
        self, *, job_id: UUID, claimed_by: str, claim_token: UUID, external_job_id: str
    ) -> MusicDirectorProviderExecution:
        external = _identifier(external_job_id, 256)
        try:
            with self._session_factory() as session, session.begin():
                self._require_claim(session, job_id, claimed_by, claim_token)
                repository = MusicDirectorProviderExecutionRepository(session)
                execution = repository.get_for_job(job_id)
                if execution is None:
                    raise ProviderExecutionError(ProviderExecutionErrorCode.NOT_FOUND)
                if execution.external_job_id is not None:
                    if execution.external_job_id != external:
                        raise ProviderExecutionError(ProviderExecutionErrorCode.IDENTITY_MISMATCH)
                    return execution
                bound = repository.bind_external_id(
                    execution.provider_execution_id,
                    expected_version=execution.version,
                    external_job_id=external,
                )
                if bound is None:
                    raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT)
                return bound
        except IntegrityError:
            raise ProviderExecutionError(ProviderExecutionErrorCode.IDENTITY_MISMATCH) from None

    def transition(
        self,
        *,
        job_id: UUID,
        claimed_by: str,
        claim_token: UUID,
        from_status: MusicDirectorProviderExecutionStatus,
        to_status: MusicDirectorProviderExecutionStatus,
    ) -> MusicDirectorProviderExecution:
        with self._session_factory() as session, session.begin():
            self._require_claim(session, job_id, claimed_by, claim_token)
            repository = MusicDirectorProviderExecutionRepository(session)
            execution = repository.get_for_job(job_id)
            if execution is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.NOT_FOUND)
            if execution.status in _TERMINAL:
                if execution.status == to_status.value:
                    return execution
                raise ProviderExecutionError(ProviderExecutionErrorCode.INVALID_TRANSITION)
            changed = repository.transition(
                execution.provider_execution_id,
                expected_version=execution.version,
                from_status=from_status.value,
                to_status=to_status.value,
            )
            if changed is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.INVALID_TRANSITION)
            return changed

    def cancel_before_submit(
        self, *, job_id: UUID, claimed_by: str, claim_token: UUID
    ) -> MusicDirectorProviderExecution:
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).get_job(job_id)
            if job is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.NOT_FOUND)
            self._require_owned(job, claimed_by, claim_token, allow_cancel=True)
            if job.cancel_requested_at is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT)
            repository = MusicDirectorProviderExecutionRepository(session)
            execution = repository.get_for_job(job_id)
            if execution is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.NOT_FOUND)
            changed = repository.transition(
                execution.provider_execution_id,
                expected_version=execution.version,
                from_status=MusicDirectorProviderExecutionStatus.INTENDED.value,
                to_status=MusicDirectorProviderExecutionStatus.CANCELLED.value,
            )
            if changed is None:
                raise ProviderExecutionError(ProviderExecutionErrorCode.INVALID_TRANSITION)
            return changed

    def _require_claim(
        self, session: Session, job_id: UUID, claimed_by: str, claim_token: UUID
    ) -> None:
        job = JobRepository(session).get_job(job_id)
        if job is None:
            raise ProviderExecutionError(ProviderExecutionErrorCode.NOT_FOUND)
        self._require_owned(job, claimed_by, claim_token)

    def _require_owned(
        self, job, claimed_by: str, claim_token: UUID, *, allow_cancel: bool = False
    ) -> None:
        lease = job.lease_expires_at
        if lease is not None and lease.tzinfo is None:
            lease = lease.replace(tzinfo=UTC)
        if (
            job.job_type != MUSIC_DIRECTOR_JOB_TYPE
            or job.status is not JobStatus.RUNNING
            or job.claimed_by != claimed_by
            or job.claim_token != claim_token
            or lease is None
            or lease <= self._clock()
        ):
            raise ProviderExecutionError(ProviderExecutionErrorCode.STALE_CLAIM)
        if not allow_cancel and job.cancel_requested_at is not None:
            raise ProviderExecutionError(ProviderExecutionErrorCode.CANCELLED)

    @staticmethod
    def _require_exact(
        execution: MusicDirectorProviderExecution, provider_id: str, model_id: str | None
    ) -> None:
        if execution.provider_id != provider_id or execution.model_id != model_id:
            raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT)


def _identifier(value: object, maximum: int) -> str:
    if type(value) is not str:
        raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT)
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or _IDENTIFIER.fullmatch(normalized) is None:
        raise ProviderExecutionError(ProviderExecutionErrorCode.CONFLICT)
    return normalized
