from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.contracts.music_director import MusicIntent
from backend.contracts.music_director_proposal import validate_music_director_proposal
from backend.contracts.music_director_provider import (
    MusicDirectorProvider,
    MusicDirectorProviderRequest,
    MusicDirectorProviderStatus,
)
from backend.models.workspace import (
    Job,
    JobStatus,
    MusicDirectorCandidate,
    MusicDirectorRun,
    Workspace,
)
from backend.models.workspace.provider_execution import MusicDirectorProviderExecutionStatus
from backend.repositories.workspace import JobRepository
from backend.services.workspace.music_director_candidate_persistence_service import (
    PersistedCandidateSet,
)
from backend.services.workspace.music_director_materialization_service import (
    CandidateProposal,
    MaterializeCandidateSetRequest,
    MusicDirectorCandidateMaterializationService,
)
from backend.services.workspace.provider_execution_service import (
    MUSIC_DIRECTOR_JOB_TYPE,
    MusicDirectorProviderExecutionService,
)


class MusicDirectorWorkerErrorCode(StrEnum):
    INVALID_JOB = "MUSIC_DIRECTOR_JOB_INVALID"
    STALE_CLAIM = "MUSIC_DIRECTOR_STALE_CLAIM"
    CANCELLED = "MUSIC_DIRECTOR_CANCELLED"
    PROVIDER_FAILED = "MUSIC_DIRECTOR_PROVIDER_FAILED"
    PROVIDER_RESULT_INVALID = "MUSIC_DIRECTOR_PROVIDER_RESULT_INVALID"


class MusicDirectorWorkerError(RuntimeError):
    def __init__(self, code: MusicDirectorWorkerErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class MusicDirectorWorkerService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        provider: MusicDirectorProvider,
        provider_executions: MusicDirectorProviderExecutionService,
        materialization: MusicDirectorCandidateMaterializationService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._provider_executions = provider_executions
        self._materialization = materialization
        self._clock = clock

    def execute_owned_claim(
        self, *, job_id: UUID, claimed_by: str, claim_token: UUID
    ) -> PersistedCandidateSet:
        replay = self._completed_replay(job_id)
        if replay is not None:
            return replay
        self._finish_pre_submit_cancellation(job_id, claimed_by, claim_token)
        job, owner_id, intent = self._job_authority(job_id, claimed_by, claim_token)
        execution = self._provider_executions.create_or_replay_intent(
            job_id=job_id,
            claimed_by=claimed_by,
            claim_token=claim_token,
            provider_id=self._provider.provider_id,
            model_id=job.model_manifest_id,
        )
        request = MusicDirectorProviderRequest(
            execution.client_execution_key,
            job.composition_snapshot_id,
            intent,
            job.model_manifest_id,
        )
        try:
            submission = self._provider.submit(request)
            execution = self._provider_executions.bind_external_id(
                job_id=job_id,
                claimed_by=claimed_by,
                claim_token=claim_token,
                external_job_id=submission.external_execution_id,
            )
            if execution.status == MusicDirectorProviderExecutionStatus.INTENDED.value:
                execution = self._provider_executions.transition(
                    job_id=job_id,
                    claimed_by=claimed_by,
                    claim_token=claim_token,
                    from_status=MusicDirectorProviderExecutionStatus.INTENDED,
                    to_status=MusicDirectorProviderExecutionStatus.SUBMITTED,
                )
            status = self._provider.read_status(submission.external_execution_id)
            if status is MusicDirectorProviderStatus.FAILED:
                self._transition_terminal(
                    job_id,
                    claimed_by,
                    claim_token,
                    execution.status,
                    MusicDirectorProviderExecutionStatus.FAILED,
                )
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.PROVIDER_FAILED)
            if status is MusicDirectorProviderStatus.CANCELLED:
                self._transition_terminal(
                    job_id,
                    claimed_by,
                    claim_token,
                    execution.status,
                    MusicDirectorProviderExecutionStatus.CANCELLED,
                )
                self._finish(job_id, claimed_by, claim_token, JobStatus.CANCELLED)
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.PROVIDER_FAILED)
            if status is not MusicDirectorProviderStatus.SUCCEEDED:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.PROVIDER_FAILED)
            result = self._provider.read_result(submission.external_execution_id)
            candidates = self._validated_candidates(job, intent, result.candidates)
            self._transition_terminal(
                job_id,
                claimed_by,
                claim_token,
                execution.status,
                MusicDirectorProviderExecutionStatus.SUCCEEDED,
            )
            persisted = self._materialization.materialize(
                MaterializeCandidateSetRequest(
                    job_id,
                    job.project_id,
                    job.composition_snapshot_id,
                    owner_id,
                    claimed_by,
                    claim_token,
                    candidates,
                    self._provider.provider_id,
                    job.model_manifest_id,
                )
            )
            self._finish(job_id, claimed_by, claim_token, JobStatus.SUCCEEDED)
            return persisted
        except MusicDirectorWorkerError:
            self._fail_if_owned(job_id, claimed_by, claim_token)
            raise
        except Exception as error:
            self._fail_if_owned(job_id, claimed_by, claim_token)
            raise MusicDirectorWorkerError(
                MusicDirectorWorkerErrorCode.PROVIDER_RESULT_INVALID
            ) from error

    def _job_authority(self, job_id: UUID, claimed_by: str, claim_token: UUID):
        with self._session_factory() as session:
            job = JobRepository(session).get_job(job_id)
            if (
                job is not None
                and job.status is JobStatus.RUNNING
                and (job.claimed_by != claimed_by or job.claim_token != claim_token)
            ):
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.STALE_CLAIM)
            if (
                job is None
                or job.job_type != MUSIC_DIRECTOR_JOB_TYPE
                or job.status is not JobStatus.RUNNING
                or job.claimed_by != claimed_by
                or job.claim_token != claim_token
                or job.cancel_requested_at is not None
                or job.composition_snapshot_id is None
            ):
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB)
            owner_id = session.scalar(
                select(Workspace.owner_id).where(Workspace.workspace_id == job.workspace_id)
            )
            if owner_id is None:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB)
            try:
                intent = MusicIntent(**job.settings_snapshot["music_intent"])
            except (KeyError, TypeError, ValueError):
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB) from None
            session.expunge(job)
            return job, owner_id, intent

    def _finish_pre_submit_cancellation(
        self, job_id: UUID, claimed_by: str, claim_token: UUID
    ) -> None:
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).get_job(job_id)
            if job is None:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB)
            if job.status is JobStatus.CANCELLED:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.CANCELLED)
            if job.status is not JobStatus.RUNNING:
                return
            if job.claimed_by != claimed_by or job.claim_token != claim_token:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.STALE_CLAIM)
            if job.cancel_requested_at is None:
                return
            finished = JobRepository(session).finish_owned_claim(
                job_id,
                claimed_by=claimed_by,
                claim_token=claim_token,
                status=JobStatus.CANCELLED,
                now=self._clock(),
            )
            if finished is None:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.STALE_CLAIM)
        raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.CANCELLED)

    def _validated_candidates(self, job, intent, raw):
        if len(raw) != intent.candidate_count or [item.ordinal for item in raw] != list(
            range(intent.candidate_count)
        ):
            raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.PROVIDER_RESULT_INVALID)
        with self._session_factory() as session:
            proposals = tuple(
                CandidateProposal(
                    item.ordinal,
                    validate_music_director_proposal(session, item.proposal),
                )
                for item in raw
            )
        if any(
            item.proposal.source_snapshot_id != job.composition_snapshot_id for item in proposals
        ):
            raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.PROVIDER_RESULT_INVALID)
        return proposals

    def _transition_terminal(self, job_id, claimed_by, claim_token, current, target):
        self._provider_executions.transition(
            job_id=job_id,
            claimed_by=claimed_by,
            claim_token=claim_token,
            from_status=MusicDirectorProviderExecutionStatus(current),
            to_status=target,
        )

    def _finish(self, job_id, claimed_by, claim_token, status):
        with self._session_factory() as session, session.begin():
            if (
                JobRepository(session).finish_owned_claim(
                    job_id,
                    claimed_by=claimed_by,
                    claim_token=claim_token,
                    status=status,
                    now=self._clock(),
                )
                is None
            ):
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB)

    def _fail_if_owned(self, job_id, claimed_by, claim_token):
        with self._session_factory() as session, session.begin():
            JobRepository(session).finish_owned_claim(
                job_id,
                claimed_by=claimed_by,
                claim_token=claim_token,
                status=JobStatus.FAILED,
                now=self._clock(),
                error_code="MUSIC_DIRECTOR_EXECUTION_FAILED",
                error_message="Music Director execution failed.",
                error_retryable=False,
            )

    def _completed_replay(self, job_id: UUID) -> PersistedCandidateSet | None:
        with self._session_factory() as session:
            job = session.get(Job, job_id)
            if job is None or job.status is not JobStatus.SUCCEEDED:
                return None
            run = session.scalar(select(MusicDirectorRun).where(MusicDirectorRun.job_id == job_id))
            if run is None:
                raise MusicDirectorWorkerError(MusicDirectorWorkerErrorCode.INVALID_JOB)
            candidates = tuple(
                session.scalars(
                    select(MusicDirectorCandidate)
                    .where(MusicDirectorCandidate.run_id == run.run_id)
                    .order_by(MusicDirectorCandidate.ordinal)
                )
            )
            session.expunge(run)
            for candidate in candidates:
                session.expunge(candidate)
            return PersistedCandidateSet(run, candidates, True)
