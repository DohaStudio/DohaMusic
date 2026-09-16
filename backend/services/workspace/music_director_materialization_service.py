from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.contracts.music_director_proposal import CanonicalMusicDirectorProposal
from backend.models.workspace import (
    Asset,
    AssetType,
    AssetVersion,
    MusicDirectorCandidateMaterialization,
    MusicDirectorMaterializationStatus,
    ProjectAsset,
)
from backend.repositories.workspace import AssetRepository, WorkspaceRepository
from backend.repositories.workspace.music_director_repository import MusicDirectorRepository
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionService,
    TrustedAdoptedArtifactRegistrationRequest,
)
from backend.services.workspace.music_director_candidate_persistence_service import (
    CandidatePersistenceFact,
    MusicDirectorCandidatePersistenceService,
    MusicDirectorPersistenceError,
    MusicDirectorPersistenceErrorCode,
    PersistCandidateSetRequest,
    PersistedCandidateSet,
)
from backend.storage.artifact_publisher import (
    ArtifactPublishError,
    LocalArtifactPublisher,
    TrustedPublicationIdentity,
)


@dataclass(frozen=True, slots=True)
class CandidateProposal:
    ordinal: int
    proposal: CanonicalMusicDirectorProposal


@dataclass(frozen=True, slots=True)
class MaterializeCandidateSetRequest:
    job_id: UUID
    project_id: UUID
    composition_snapshot_id: UUID
    effective_owner_id: UUID
    claimed_by: str
    claim_token: UUID
    candidates: tuple[CandidateProposal, ...]
    provider: str | None = None
    model: str | None = None


class MusicDirectorCandidateMaterializationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        publisher: LocalArtifactPublisher,
        artifact_ingestion: ArtifactIngestionService,
        staging_root: Path,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._artifact_ingestion = artifact_ingestion
        self._staging_root = staging_root

    def materialize(self, request: MaterializeCandidateSetRequest) -> PersistedCandidateSet:
        self._validate_shape(request)
        intents = self._intend(request)
        for proposal, intent in zip(request.candidates, intents, strict=True):
            self._publish(proposal, intent)
        try:
            return self._complete(request)
        except IntegrityError as error:
            try:
                return self._replay_completed(request)
            except MusicDirectorPersistenceError as replay_error:
                raise replay_error from error

    def _intend(
        self, request: MaterializeCandidateSetRequest
    ) -> tuple[MusicDirectorCandidateMaterialization, ...]:
        try:
            with self._session_factory() as session, session.begin():
                repository = MusicDirectorRepository(session)
                existing = repository.list_materializations(request.job_id)
                if existing:
                    return self._validate_intent_replay(request, existing)
                run_id = uuid4()
                items = []
                validation_facts = []
                for candidate in request.candidates:
                    identity = TrustedPublicationIdentity.for_music_director_proposal(
                        request.job_id, candidate.ordinal, candidate.proposal.digest
                    )
                    item = MusicDirectorCandidateMaterialization(
                        job_id=request.job_id,
                        ordinal=candidate.ordinal,
                        materialization_key=_materialization_key(
                            request.job_id, candidate.ordinal, candidate.proposal.digest
                        ),
                        proposal_digest=candidate.proposal.digest,
                        planned_run_id=run_id,
                        planned_candidate_id=uuid4(),
                        planned_asset_id=uuid4(),
                        planned_asset_version_id=uuid4(),
                        planned_artifact_id=uuid4(),
                        storage_domain=identity.storage_domain,
                        storage_key=identity.storage_key,
                        status=MusicDirectorMaterializationStatus.INTENDED.value,
                    )
                    items.append(item)
                    validation_facts.append(
                        CandidatePersistenceFact(
                            item.ordinal,
                            item.proposal_digest,
                            item.planned_asset_version_id,
                            item.planned_artifact_id,
                        )
                    )
                persistence_request = self._persistence_request(request, tuple(validation_facts))
                MusicDirectorCandidatePersistenceService.validate_job_in_session(
                    session, persistence_request
                )
                repository.add_materializations(items)
                return tuple(items)
        except IntegrityError as error:
            with self._session_factory() as session:
                existing = MusicDirectorRepository(session).list_materializations(request.job_id)
                if existing:
                    return self._validate_intent_replay(request, existing)
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.CONFLICT
            ) from error

    def _publish(
        self,
        candidate: CandidateProposal,
        intent: MusicDirectorCandidateMaterialization,
    ) -> None:
        already_authoritative = intent.status in {
            MusicDirectorMaterializationStatus.PUBLISHED.value,
            MusicDirectorMaterializationStatus.COMPLETED.value,
        }
        identity = TrustedPublicationIdentity.for_music_director_proposal(
            intent.job_id, intent.ordinal, intent.proposal_digest
        )
        if (
            identity.storage_domain != intent.storage_domain
            or identity.storage_key != intent.storage_key
        ):
            self._reconciliation_required(intent.materialization_id)
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
        staged = self._staging_root / (f"music-director-{intent.materialization_id}-{uuid4()}.json")
        staged.write_bytes(candidate.proposal.canonical_bytes)
        try:
            self._publisher.publish_or_adopt(
                staged,
                identity=identity,
                artifact_kind="manifest",
                expected_media_type="application/json",
                expected_sha256=intent.proposal_digest,
                expected_size_bytes=len(candidate.proposal.canonical_bytes),
            )
        except ArtifactPublishError:
            self._reconciliation_required(intent.materialization_id)
            raise
        finally:
            staged.unlink(missing_ok=True)
        if already_authoritative:
            return
        with self._session_factory() as session, session.begin():
            current = session.get(MusicDirectorCandidateMaterialization, intent.materialization_id)
            if current is None:
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            if current.status in {
                MusicDirectorMaterializationStatus.PUBLISHED.value,
                MusicDirectorMaterializationStatus.COMPLETED.value,
            }:
                return
            if current.status != MusicDirectorMaterializationStatus.INTENDED.value:
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            current.status = MusicDirectorMaterializationStatus.PUBLISHED.value
            current.version += 1

    def _complete(self, request: MaterializeCandidateSetRequest) -> PersistedCandidateSet:
        with self._session_factory() as session, session.begin():
            repository = MusicDirectorRepository(session)
            intents = repository.list_materializations(request.job_id)
            self._validate_intent_replay(request, intents)
            if any(
                item.status
                not in {
                    MusicDirectorMaterializationStatus.PUBLISHED.value,
                    MusicDirectorMaterializationStatus.COMPLETED.value,
                }
                for item in intents
            ):
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            project = WorkspaceRepository(session).get_project(request.project_id)
            if project is None:
                raise MusicDirectorPersistenceError(
                    MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH
                )
            assets = AssetRepository(session)
            facts = []
            for candidate, intent in zip(request.candidates, intents, strict=True):
                if assets.get_asset(intent.planned_asset_id) is None:
                    assets.add_asset(
                        Asset(
                            asset_id=intent.planned_asset_id,
                            workspace_id=project.workspace_id,
                            owner_id=request.effective_owner_id,
                            asset_type=AssetType.CANDIDATE,
                            lifecycle_status="active",
                        )
                    )
                    WorkspaceRepository(session).add_project_asset(
                        ProjectAsset(
                            project_id=request.project_id,
                            asset_id=intent.planned_asset_id,
                            role="music_director_candidate",
                            display_order=intent.ordinal,
                        )
                    )
                    assets.add_asset_version(
                        AssetVersion(
                            asset_version_id=intent.planned_asset_version_id,
                            asset_id=intent.planned_asset_id,
                            version_number=1,
                            version_origin="music_director",
                            settings_snapshot={
                                "proposal_digest": intent.proposal_digest,
                                "source_snapshot_id": str(request.composition_snapshot_id),
                            },
                            created_by=request.effective_owner_id,
                        )
                    )
                    identity = TrustedPublicationIdentity.for_music_director_proposal(
                        request.job_id, intent.ordinal, intent.proposal_digest
                    )
                    self._artifact_ingestion.register_trusted_adopted_in_session(
                        session,
                        TrustedAdoptedArtifactRegistrationRequest(
                            artifact_id=intent.planned_artifact_id,
                            asset_version_id=intent.planned_asset_version_id,
                            identity=identity,
                            artifact_kind="manifest",
                            producer_type="music_director",
                            expected_media_type="application/json",
                            expected_sha256=intent.proposal_digest,
                            expected_size_bytes=len(candidate.proposal.canonical_bytes),
                            producer_id=request.provider,
                            run_id=str(intent.planned_run_id),
                        ),
                    )
                facts.append(
                    CandidatePersistenceFact(
                        intent.ordinal,
                        intent.proposal_digest,
                        intent.planned_asset_version_id,
                        intent.planned_artifact_id,
                        provider=request.provider,
                        model=request.model,
                    )
                )
            result = MusicDirectorCandidatePersistenceService(
                self._session_factory
            ).persist_in_session(
                session,
                self._persistence_request(request, tuple(facts)),
                planned_run_id=intents[0].planned_run_id,
                planned_candidate_ids=tuple(item.planned_candidate_id for item in intents),
            )
            for item in intents:
                item.status = MusicDirectorMaterializationStatus.COMPLETED.value
                item.version += 1
            return result

    def _reconciliation_required(self, materialization_id: UUID) -> None:
        with self._session_factory() as session, session.begin():
            item = session.get(MusicDirectorCandidateMaterialization, materialization_id)
            if item is not None:
                item.status = MusicDirectorMaterializationStatus.RECONCILIATION_REQUIRED.value
                item.version += 1

    def _replay_completed(self, request: MaterializeCandidateSetRequest) -> PersistedCandidateSet:
        with self._session_factory() as session, session.begin():
            intents = MusicDirectorRepository(session).list_materializations(request.job_id)
            self._validate_intent_replay(request, intents)
            if any(
                item.status != MusicDirectorMaterializationStatus.COMPLETED.value
                for item in intents
            ):
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            facts = tuple(
                CandidatePersistenceFact(
                    item.ordinal,
                    item.proposal_digest,
                    item.planned_asset_version_id,
                    item.planned_artifact_id,
                    provider=request.provider,
                    model=request.model,
                )
                for item in intents
            )
            result = MusicDirectorCandidatePersistenceService(
                self._session_factory
            ).persist_in_session(
                session,
                self._persistence_request(request, facts),
                planned_run_id=intents[0].planned_run_id,
                planned_candidate_ids=tuple(item.planned_candidate_id for item in intents),
            )
            if tuple(candidate.candidate_id for candidate in result.candidates) != tuple(
                item.planned_candidate_id for item in intents
            ):
                raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
            return result

    @staticmethod
    def _validate_shape(request: MaterializeCandidateSetRequest) -> None:
        if not 1 <= len(request.candidates) <= 4 or [
            item.ordinal for item in request.candidates
        ] != list(range(len(request.candidates))):
            raise MusicDirectorPersistenceError(
                MusicDirectorPersistenceErrorCode.INVALID_CARDINALITY
            )
        if any(
            item.proposal.source_snapshot_id != request.composition_snapshot_id
            for item in request.candidates
        ):
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.LINEAGE_MISMATCH)

    @staticmethod
    def _validate_intent_replay(
        request: MaterializeCandidateSetRequest,
        existing: list[MusicDirectorCandidateMaterialization],
    ) -> tuple[MusicDirectorCandidateMaterialization, ...]:
        expected = [(item.ordinal, item.proposal.digest) for item in request.candidates]
        actual = [(item.ordinal, item.proposal_digest) for item in existing]
        if expected != actual or len({item.planned_run_id for item in existing}) != 1:
            raise MusicDirectorPersistenceError(MusicDirectorPersistenceErrorCode.CONFLICT)
        return tuple(existing)

    @staticmethod
    def _persistence_request(
        request: MaterializeCandidateSetRequest,
        facts: tuple[CandidatePersistenceFact, ...],
    ) -> PersistCandidateSetRequest:
        return PersistCandidateSetRequest(
            request.job_id,
            request.project_id,
            request.composition_snapshot_id,
            request.effective_owner_id,
            request.claimed_by,
            request.claim_token,
            facts,
        )


def _materialization_key(job_id: UUID, ordinal: int, digest: str) -> str:
    return hashlib.sha256(f"{job_id}:{ordinal}:proposal:{digest}".encode()).hexdigest()
