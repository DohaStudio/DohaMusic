from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.contracts.music_director import MusicIntent
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetType,
    AssetVersion,
    CompositionSnapshot,
    JobStatus,
    ProjectAsset,
)
from backend.models.workspace.music_director import (
    MusicDirectorCandidate,
    MusicDirectorCandidateStatus,
    MusicDirectorRun,
)
from backend.repositories.workspace import JobRepository, WorkspaceRepository
from backend.repositories.workspace.music_director_repository import MusicDirectorRepository

MUSIC_DIRECTOR_JOB_TYPE = "music_director"
MUSIC_DIRECTOR_CANDIDATE_ROLE = "music_director_candidate"
PROPOSAL_MEDIA_TYPE = "application/json"
PREVIEW_MEDIA_TYPES = frozenset({"audio/wav", "audio/flac", "audio/mpeg"})


class MusicDirectorPersistenceErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    STALE_CLAIM = "STALE_CLAIM"
    CANCELLED = "CANCELLED"
    INVALID_CARDINALITY = "INVALID_CARDINALITY"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    STALE_SELECTION = "STALE_SELECTION"
    INVALID_TRANSITION = "INVALID_TRANSITION"


class MusicDirectorPersistenceError(RuntimeError):
    def __init__(self, code: MusicDirectorPersistenceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class CandidatePersistenceFact:
    ordinal: int
    proposal_digest: str
    candidate_asset_version_id: UUID
    proposal_artifact_id: UUID
    preview_artifact_id: UUID | None = None
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class PersistCandidateSetRequest:
    job_id: UUID
    project_id: UUID
    composition_snapshot_id: UUID
    effective_owner_id: UUID
    claimed_by: str
    claim_token: UUID
    candidates: tuple[CandidatePersistenceFact, ...]


@dataclass(frozen=True, slots=True)
class PersistedCandidateSet:
    run: MusicDirectorRun
    candidates: tuple[MusicDirectorCandidate, ...]
    replayed: bool


class MusicDirectorCandidatePersistenceService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def persist(self, request: PersistCandidateSetRequest) -> PersistedCandidateSet:
        self._validate_candidate_shape(request.candidates)
        try:
            with self._session_factory() as session, session.begin():
                return self.persist_in_session(session, request)
        except IntegrityError as error:
            replay = self._replay_fresh(request)
            if replay is not None:
                return replay
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.CONFLICT
            ) from error

    def persist_in_session(
        self,
        session: Session,
        request: PersistCandidateSetRequest,
        *,
        planned_run_id: UUID | None = None,
        planned_candidate_ids: tuple[UUID, ...] | None = None,
    ) -> PersistedCandidateSet:
        """Persist one exact Candidate set without owning commit or rollback."""
        self._validate_candidate_shape(request.candidates)
        if planned_candidate_ids is not None and len(planned_candidate_ids) != len(
            request.candidates
        ):
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.INVALID_CARDINALITY
            )
        self.validate_job_in_session(session, request)
        repository = MusicDirectorRepository(session)
        existing = repository.get_run_for_job(request.job_id)
        if existing is not None:
            replay = self._exact_replay(repository, existing, request)
            self._validate_lineage(session, request)
            if planned_run_id is not None and existing.run_id != planned_run_id:
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            return replay
        self._validate_lineage(session, request)
        run = MusicDirectorRun(
            run_id=planned_run_id or uuid4(),
            job_id=request.job_id,
            project_id=request.project_id,
            composition_snapshot_id=request.composition_snapshot_id,
        )
        candidates = [
            MusicDirectorCandidate(
                candidate_id=(
                    planned_candidate_ids[index] if planned_candidate_ids is not None else uuid4()
                ),
                run_id=run.run_id,
                ordinal=fact.ordinal,
                status="generated",
                proposal_digest=fact.proposal_digest,
                candidate_asset_version_id=fact.candidate_asset_version_id,
                proposal_artifact_id=fact.proposal_artifact_id,
                preview_artifact_id=fact.preview_artifact_id,
                provider=fact.provider,
                model=fact.model,
            )
            for index, fact in enumerate(request.candidates)
        ]
        repository.add_run(run)
        repository.add_candidates(candidates)
        return PersistedCandidateSet(run, tuple(candidates), False)

    def select(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
        expected_version: int,
    ) -> MusicDirectorRun:
        with self._session_factory() as session, session.begin():
            repository = MusicDirectorRepository(session)
            run, candidate = self._selection_scope(
                repository, project_id=project_id, run_id=run_id, candidate_id=candidate_id
            )
            if run.applied_candidate_id is not None:
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.INVALID_TRANSITION
                )
            if candidate.status != MusicDirectorCandidateStatus.GENERATED.value:
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.INVALID_TRANSITION
                )
            if run.selected_candidate_id == candidate_id:
                return run
            if not repository.select_candidate(
                run_id=run_id,
                candidate_id=candidate_id,
                expected_version=expected_version,
            ):
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.STALE_SELECTION
                )
            session.flush()
            return repository.get_run(run_id)  # type: ignore[return-value]

    def reject(
        self, *, project_id: UUID, run_id: UUID, candidate_id: UUID
    ) -> MusicDirectorCandidate:
        with self._session_factory() as session, session.begin():
            repository = MusicDirectorRepository(session)
            run, candidate = self._selection_scope(
                repository, project_id=project_id, run_id=run_id, candidate_id=candidate_id
            )
            if candidate.status == MusicDirectorCandidateStatus.REJECTED.value:
                return candidate
            if (
                candidate.status != MusicDirectorCandidateStatus.GENERATED.value
                or run.applied_candidate_id == candidate_id
            ):
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.INVALID_TRANSITION
                )
            if not repository.transition_candidate_status(
                candidate_id=candidate_id,
                from_status=MusicDirectorCandidateStatus.GENERATED.value,
                to_status=MusicDirectorCandidateStatus.REJECTED.value,
            ):
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.INVALID_TRANSITION
                )
            session.flush()
            return repository.get_candidate(candidate_id)  # type: ignore[return-value]

    def _replay_fresh(self, request: PersistCandidateSetRequest) -> PersistedCandidateSet | None:
        with self._session_factory() as session:
            repository = MusicDirectorRepository(session)
            run = repository.get_run_for_job(request.job_id)
            return self._exact_replay(repository, run, request) if run is not None else None

    @staticmethod
    def _validate_candidate_shape(candidates: tuple[CandidatePersistenceFact, ...]) -> None:
        if not 1 <= len(candidates) <= 4:
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.INVALID_CARDINALITY
            )
        if [item.ordinal for item in candidates] != list(range(len(candidates))):
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.INVALID_CARDINALITY
            )

    @staticmethod
    def validate_job_in_session(session: Session, request: PersistCandidateSetRequest) -> None:
        job = JobRepository(session).get_job(request.job_id)
        if job is None:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.NOT_FOUND)
        if (
            job.job_type != MUSIC_DIRECTOR_JOB_TYPE
            or job.project_id != request.project_id
            or job.composition_snapshot_id != request.composition_snapshot_id
        ):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
        snapshot = session.get(CompositionSnapshot, request.composition_snapshot_id)
        project = WorkspaceRepository(session).get_project(request.project_id)
        workspace = (
            WorkspaceRepository(session).get_workspace(project.workspace_id)
            if project is not None
            else None
        )
        if (
            snapshot is None
            or snapshot.project_id != request.project_id
            or project is None
            or workspace is None
            or workspace.owner_id != request.effective_owner_id
        ):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH)
        try:
            intent = MusicIntent(**job.settings_snapshot["music_intent"])
        except (KeyError, TypeError, ValueError):
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.CONFLICT
            ) from None
        if intent.candidate_count != len(request.candidates):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
        if job.cancel_requested_at is not None:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CANCELLED)
        now = datetime.now(UTC)
        lease = job.lease_expires_at
        if lease is not None and lease.tzinfo is None:
            lease = lease.replace(tzinfo=UTC)
        if (
            job.status is not JobStatus.RUNNING
            or job.claimed_by != request.claimed_by
            or job.claim_token != request.claim_token
            or lease is None
            or lease <= now
        ):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.STALE_CLAIM)

    @staticmethod
    def _validate_lineage(session: Session, request: PersistCandidateSetRequest) -> None:
        project = WorkspaceRepository(session).get_project(request.project_id)
        if project is None:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH)
        for fact in request.candidates:
            version = session.get(AssetVersion, fact.candidate_asset_version_id)
            asset = session.get(Asset, version.asset_id) if version is not None else None
            membership = (
                session.scalar(
                    select(ProjectAsset).where(
                        ProjectAsset.project_id == request.project_id,
                        ProjectAsset.asset_id == asset.asset_id,
                        ProjectAsset.deleted_at.is_(None),
                        ProjectAsset.role == MUSIC_DIRECTOR_CANDIDATE_ROLE,
                    )
                )
                if asset is not None
                else None
            )
            proposal = session.get(Artifact, fact.proposal_artifact_id)
            preview = (
                session.get(Artifact, fact.preview_artifact_id)
                if fact.preview_artifact_id is not None
                else None
            )
            artifacts = (proposal,) if preview is None else (proposal, preview)
            locations_valid = all(
                artifact is not None
                and session.scalar(
                    select(ArtifactStorageLocation).where(
                        ArtifactStorageLocation.artifact_id == artifact.artifact_id
                    )
                )
                is not None
                for artifact in artifacts
            )
            if (
                version is None
                or asset is None
                or asset.asset_type is not AssetType.CANDIDATE
                or asset.workspace_id != project.workspace_id
                or asset.owner_id != request.effective_owner_id
                or asset.lifecycle_status != "active"
                or asset.deleted_at is not None
                or membership is None
                or proposal is None
                or proposal.asset_version_id != version.asset_version_id
                or proposal.media_type != PROPOSAL_MEDIA_TYPE
                or proposal.checksum_algorithm.lower() != "sha256"
                or proposal.artifact_checksum != fact.proposal_digest
                or proposal.retention_status != "active"
                or (preview is not None and preview.asset_version_id != version.asset_version_id)
                or (preview is not None and preview.media_type not in PREVIEW_MEDIA_TYPES)
                or (preview is not None and preview.retention_status != "active")
                or not locations_valid
            ):
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
                )

    @staticmethod
    def _exact_replay(
        repository: MusicDirectorRepository,
        run: MusicDirectorRun,
        request: PersistCandidateSetRequest,
    ) -> PersistedCandidateSet:
        candidates = repository.list_candidates(run.run_id)
        expected = [
            (
                fact.ordinal,
                fact.proposal_digest,
                fact.candidate_asset_version_id,
                fact.proposal_artifact_id,
                fact.preview_artifact_id,
                fact.provider,
                fact.model,
            )
            for fact in request.candidates
        ]
        actual = [
            (
                item.ordinal,
                item.proposal_digest,
                item.candidate_asset_version_id,
                item.proposal_artifact_id,
                item.preview_artifact_id,
                item.provider,
                item.model,
            )
            for item in candidates
        ]
        if (
            run.project_id != request.project_id
            or run.composition_snapshot_id != request.composition_snapshot_id
            or actual != expected
        ):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
        return PersistedCandidateSet(run, tuple(candidates), True)

    @staticmethod
    def _selection_scope(
        repository: MusicDirectorRepository,
        *,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
    ) -> tuple[MusicDirectorRun, MusicDirectorCandidate]:
        run = repository.get_run(run_id)
        candidate = repository.get_candidate(candidate_id)
        if run is None or candidate is None:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.NOT_FOUND)
        if run.project_id != project_id or candidate.run_id != run_id:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH)
        return run, candidate
