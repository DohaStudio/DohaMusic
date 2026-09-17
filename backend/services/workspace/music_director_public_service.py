from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.contracts.music_director import MusicIntent
from backend.models.workspace import Job, JobStatus, MusicProject, Workspace
from backend.models.workspace.music_director import MusicDirectorCandidate, MusicDirectorRun
from backend.repositories.workspace.music_director_repository import MusicDirectorRepository
from backend.services.workspace.job_service import JobCreation, JobService
from backend.services.workspace.music_director_candidate_persistence_service import (
    MusicDirectorCandidatePersistenceService,
)


class MusicDirectorPublicErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    NOT_READY = "NOT_READY"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"


class MusicDirectorPublicError(RuntimeError):
    def __init__(self, code: MusicDirectorPublicErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class PublicMusicDirectorRun:
    run: MusicDirectorRun
    job: Job
    candidates: tuple[MusicDirectorCandidate, ...]


class MusicDirectorPublicService:
    def __init__(self, session_factory: sessionmaker[Session], job_service: JobService) -> None:
        self._session_factory = session_factory
        self._jobs = job_service
        self._candidates = MusicDirectorCandidatePersistenceService(session_factory)

    def create_run_job(
        self,
        *,
        effective_owner_id: UUID,
        project_id: UUID,
        composition_snapshot_id: UUID,
        instruction: str,
        candidate_count: int,
        idempotency_key: str,
    ) -> JobCreation:
        intent = MusicIntent(instruction=instruction, candidate_count=candidate_count)
        return self._jobs.create_job_for_owner(
            effective_owner_id=effective_owner_id,
            project_id=project_id,
            job_type="music_director",
            api_contract_version="1",
            settings_snapshot={
                "music_intent": {
                    "instruction": intent.instruction,
                    "candidate_count": intent.candidate_count,
                }
            },
            idempotency_key=idempotency_key,
            composition_snapshot_id=composition_snapshot_id,
        )

    def get_run(
        self, *, effective_owner_id: UUID, project_id: UUID, run_id: UUID
    ) -> PublicMusicDirectorRun:
        with self._session_factory() as session:
            repository = MusicDirectorRepository(session)
            run = repository.get_run(run_id)
            if run is None:
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.NOT_FOUND)
            job = session.get(Job, run.job_id)
            if job is None or not self._owns_project(session, project_id, effective_owner_id):
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.NOT_FOUND)
            if run.project_id != project_id or job.project_id != project_id:
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.LINEAGE_MISMATCH)
            candidates = tuple(repository.list_candidates(run_id))
            expected = job.settings_snapshot.get("music_intent", {}).get("candidate_count")
            if job.status is not JobStatus.SUCCEEDED or expected != len(candidates):
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.NOT_READY)
            session.expunge(run)
            session.expunge(job)
            for candidate in candidates:
                session.expunge(candidate)
            return PublicMusicDirectorRun(run, job, candidates)

    def get_candidate(
        self, *, effective_owner_id: UUID, project_id: UUID, run_id: UUID, candidate_id: UUID
    ) -> tuple[PublicMusicDirectorRun, MusicDirectorCandidate]:
        aggregate = self.get_run(
            effective_owner_id=effective_owner_id, project_id=project_id, run_id=run_id
        )
        candidate = next(
            (item for item in aggregate.candidates if item.candidate_id == candidate_id), None
        )
        if candidate is None:
            raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.LINEAGE_MISMATCH)
        return aggregate, candidate

    def select_candidate(
        self,
        *,
        effective_owner_id: UUID,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
        expected_version: int,
    ) -> MusicDirectorRun:
        self.get_candidate(
            effective_owner_id=effective_owner_id,
            project_id=project_id,
            run_id=run_id,
            candidate_id=candidate_id,
        )
        return self._candidates.select(
            project_id=project_id,
            run_id=run_id,
            candidate_id=candidate_id,
            expected_version=expected_version,
        )

    def cancel_job(self, *, effective_owner_id: UUID, project_id: UUID, job_id: UUID):
        with self._session_factory() as session:
            job = session.get(Job, job_id)
            if (
                job is None
                or job.project_id != project_id
                or not self._owns_project(session, project_id, effective_owner_id)
            ):
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.NOT_FOUND)
            if job.job_type != "music_director":
                raise MusicDirectorPublicError(MusicDirectorPublicErrorCode.LINEAGE_MISMATCH)
        return self._jobs.cancel_job_for_owner(job_id, effective_owner_id=effective_owner_id)

    @staticmethod
    def _owns_project(session: Session, project_id: UUID, owner_id: UUID) -> bool:
        return (
            session.scalar(
                select(MusicProject.project_id)
                .join(Workspace, Workspace.workspace_id == MusicProject.workspace_id)
                .where(MusicProject.project_id == project_id, Workspace.owner_id == owner_id)
            )
            is not None
        )
