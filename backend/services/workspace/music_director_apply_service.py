from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.contracts.music_director_proposal import (
    MusicDirectorProposalError,
    validate_music_director_proposal,
)
from backend.core.idempotency_completion import (
    IdempotencyCompletionResult,
    IdempotencyResultType,
)
from backend.models.workspace import (
    Artifact,
    CompositionClip,
    CompositionTrack,
    Job,
    JobStatus,
    MusicProject,
    WorkingComposition,
    Workspace,
)
from backend.models.workspace.music_director import (
    MusicDirectorCandidate,
    MusicDirectorMaterializationStatus,
    MusicDirectorRun,
)
from backend.repositories.idempotency_repository import IdempotencyRepository
from backend.repositories.workspace import (
    ArtifactStorageRepository,
    CompositionHistoryRepository,
    CompositionRepository,
)
from backend.repositories.workspace.music_director_repository import MusicDirectorRepository
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
)

MUSIC_DIRECTOR_APPLY_CONTRACT_VERSION = 1


class MusicDirectorApplyErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    NOT_READY = "NOT_READY"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    IDEMPOTENCY_IN_PROGRESS = "IDEMPOTENCY_IN_PROGRESS"
    STALE_RUN = "STALE_RUN"
    STALE_WORKING_COMPOSITION = "STALE_WORKING_COMPOSITION"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    ARTIFACT_MISMATCH = "ARTIFACT_MISMATCH"
    ALREADY_APPLIED = "ALREADY_APPLIED"


class MusicDirectorApplyError(RuntimeError):
    def __init__(self, code: MusicDirectorApplyErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class MusicDirectorApplyResult:
    run_id: UUID
    candidate_id: UUID
    working_composition_id: UUID
    working_composition_revision: int
    run_version: int
    history_entry_id: UUID
    replayed: bool


class MusicDirectorApplyService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        artifact_roots: ArtifactStorageRoots,
    ) -> None:
        self._session_factory = session_factory
        self._artifact_roots = artifact_roots

    def apply(
        self,
        *,
        effective_owner_id: UUID,
        project_id: UUID,
        run_id: UUID,
        candidate_id: UUID,
        expected_run_version: int,
        expected_working_composition_revision: int,
        idempotency_key: str,
    ) -> MusicDirectorApplyResult:
        with self._session_factory() as session, session.begin():
            run, candidate, job, working = self._load_authority(
                session=session,
                owner_id=effective_owner_id,
                project_id=project_id,
                run_id=run_id,
                candidate_id=candidate_id,
            )
            fingerprint = self._fingerprint(
                effective_owner_id=effective_owner_id,
                project_id=project_id,
                run_id=run_id,
                candidate_id=candidate_id,
                working_composition_id=working.working_composition_id,
                expected_run_version=expected_run_version,
                expected_working_composition_revision=expected_working_composition_revision,
                proposal_artifact_id=candidate.proposal_artifact_id,
                apply_contract_version=MUSIC_DIRECTOR_APPLY_CONTRACT_VERSION,
                proposal_schema_version=1,
                proposal_digest=candidate.proposal_digest,
            )
            idempotency = IdempotencyRepository(session)
            try:
                claim = idempotency.claim_with_result(
                    scope=f"music-director-apply:{project_id}",
                    key=idempotency_key,
                    fingerprint=fingerprint,
                    now=datetime.now(UTC),
                )
            except ValueError as exc:
                codes = {
                    "IDEMPOTENCY_CONFLICT": MusicDirectorApplyErrorCode.IDEMPOTENCY_CONFLICT,
                    "IDEMPOTENCY_IN_PROGRESS": MusicDirectorApplyErrorCode.IDEMPOTENCY_IN_PROGRESS,
                }
                code = codes.get(str(exc))
                if code is None:
                    raise
                raise MusicDirectorApplyError(code) from exc
            if claim.replayed:
                return self._replay(claim.completion_result, run_version=run.version)

            self._require_preconditions(
                run=run,
                candidate=candidate,
                job=job,
                working=working,
                expected_run_version=expected_run_version,
                expected_working_revision=expected_working_composition_revision,
            )
            proposal = self._read_proposal(session, run, candidate)
            before, after = self._apply_operations(session, working, proposal.operations)
            history = CompositionHistoryRepository(session).append(
                working_composition_id=working.working_composition_id,
                command_type="MUSIC_DIRECTOR_APPLY",
                target_type="WORKING_COMPOSITION",
                target_id=working.working_composition_id,
                before_state=self._history_state(run, candidate, before),
                after_state=self._history_state(run, candidate, after),
            )
            revision = CompositionRepository(session).increment_working_revision(
                working.working_composition_id,
                expected_revision=expected_working_composition_revision,
            )
            if revision is None:
                raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.STALE_WORKING_COMPOSITION)
            if not MusicDirectorRepository(session).apply_candidate(
                run_id=run_id,
                candidate_id=candidate_id,
                expected_version=expected_run_version,
                applied_working_revision=revision,
            ):
                raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.STALE_RUN)
            completion = IdempotencyCompletionResult.create(
                completed_revision=revision,
                result_type=IdempotencyResultType.MUSIC_DIRECTOR_APPLY,
                result_payload={
                    "run_id": str(run_id),
                    "candidate_id": str(candidate_id),
                    "working_composition_id": str(working.working_composition_id),
                    "history_entry_id": str(history.history_entry_id),
                },
            )
            idempotency.complete_with_result(
                claim.record,
                resource_type="music_director_candidate_apply",
                resource_id=str(candidate_id),
                response_status=200,
                completion_result=completion,
            )
            return MusicDirectorApplyResult(
                run_id,
                candidate_id,
                working.working_composition_id,
                revision,
                expected_run_version + 1,
                history.history_entry_id,
                False,
            )

    @staticmethod
    def _fingerprint(**values: object) -> str:
        payload = json.dumps(
            {key: str(value) for key, value in values.items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _load_authority(
        *, session: Session, owner_id: UUID, project_id: UUID, run_id: UUID, candidate_id: UUID
    ) -> tuple[MusicDirectorRun, MusicDirectorCandidate, Job, WorkingComposition]:
        owned = session.scalar(
            select(MusicProject.project_id)
            .join(Workspace, Workspace.workspace_id == MusicProject.workspace_id)
            .where(MusicProject.project_id == project_id, Workspace.owner_id == owner_id)
        )
        run = session.get(MusicDirectorRun, run_id)
        candidate = session.get(MusicDirectorCandidate, candidate_id)
        if owned is None or run is None or candidate is None:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_FOUND)
        if run.project_id != project_id or candidate.run_id != run_id:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.LINEAGE_MISMATCH)
        job = session.get(Job, run.job_id)
        working = session.scalar(
            select(WorkingComposition).where(WorkingComposition.project_id == project_id)
        )
        if job is None or working is None:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_READY)
        return run, candidate, job, working

    @staticmethod
    def _require_preconditions(
        *, run, candidate, job, working, expected_run_version, expected_working_revision
    ) -> None:
        if job.status is not JobStatus.SUCCEEDED:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_READY)
        if run.selected_candidate_id != candidate.candidate_id:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_READY)
        if run.applied_candidate_id is not None or candidate.status != "generated":
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.ALREADY_APPLIED)
        if run.version != expected_run_version:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.STALE_RUN)
        if working.revision != expected_working_revision:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.STALE_WORKING_COMPOSITION)
        if working.base_composition_snapshot_id != run.composition_snapshot_id:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.LINEAGE_MISMATCH)

    def _read_proposal(self, session, run, candidate):
        materializations = MusicDirectorRepository(session).list_materializations(run.job_id)
        expected_count = (
            session.get(Job, run.job_id)
            .settings_snapshot.get("music_intent", {})
            .get("candidate_count")
        )
        if (
            type(expected_count) is not int
            or len(materializations) != expected_count
            or any(
                item.status != MusicDirectorMaterializationStatus.COMPLETED.value
                for item in materializations
            )
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_READY)
        materialization = next(
            (
                item
                for item in materializations
                if item.planned_candidate_id == candidate.candidate_id
            ),
            None,
        )
        if (
            materialization is None
            or materialization.status != MusicDirectorMaterializationStatus.COMPLETED.value
            or materialization.planned_artifact_id != candidate.proposal_artifact_id
            or materialization.proposal_digest != candidate.proposal_digest
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.NOT_READY)
        artifact = session.get(Artifact, candidate.proposal_artifact_id)
        if (
            artifact is None
            or artifact.artifact_kind != "manifest"
            or artifact.media_type != "application/json"
            or artifact.artifact_checksum != candidate.proposal_digest
            or artifact.checksum_algorithm.lower() != "sha256"
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.ARTIFACT_MISMATCH)
        resolver = ArtifactStorageResolver(ArtifactStorageRepository(session), self._artifact_roots)
        try:
            with resolver.open_payload(candidate.proposal_artifact_id) as (_, stream):
                payload = stream.read()
        except ArtifactStorageError as exc:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.ARTIFACT_MISMATCH) from exc
        if (
            len(payload) != artifact.size_bytes
            or hashlib.sha256(payload).hexdigest() != candidate.proposal_digest
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.ARTIFACT_MISMATCH)
        try:
            proposal = validate_music_director_proposal(session, json.loads(payload))
        except (MusicDirectorProposalError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.INVALID_PROPOSAL) from exc
        if (
            proposal.canonical_bytes != payload
            or proposal.source_snapshot_id != run.composition_snapshot_id
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.ARTIFACT_MISMATCH)
        return proposal

    @staticmethod
    def _apply_operations(session, working, operations):
        before, after = [], []
        for operation in operations:
            kind = operation["operation"]
            if kind == "set_master_gain":
                target, old, new = None, working.master_gain_db, Decimal(str(operation["gain_db"]))
                working.master_gain_db = new
            elif kind == "set_clip_gain":
                target = operation["canonical_clip_id"]
                clip = session.scalar(
                    select(CompositionClip).where(
                        CompositionClip.working_composition_id == working.working_composition_id,
                        CompositionClip.clip_id == UUID(target),
                        CompositionClip.deleted_at.is_(None),
                    )
                )
                if clip is None:
                    raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.INVALID_PROPOSAL)
                old, new = clip.gain_db, Decimal(str(operation["gain_db"]))
                clip.gain_db = new
            else:
                target = operation["canonical_track_id"]
                track = session.scalar(
                    select(CompositionTrack).where(
                        CompositionTrack.working_composition_id == working.working_composition_id,
                        CompositionTrack.track_id == UUID(target),
                        CompositionTrack.deleted_at.is_(None),
                    )
                )
                if track is None:
                    raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.INVALID_PROPOSAL)
                attribute = "gain_db" if kind == "set_track_gain" else "pan"
                old, new = getattr(track, attribute), Decimal(str(operation[attribute]))
                setattr(track, attribute, new)
            before.append({"operation": kind, "target_id": target, "value": str(old)})
            after.append({"operation": kind, "target_id": target, "value": str(new)})
        session.flush()
        return before, after

    @staticmethod
    def _history_state(run, candidate, mutations):
        return {
            "run_id": str(run.run_id),
            "candidate_id": str(candidate.candidate_id),
            "source_snapshot_id": str(run.composition_snapshot_id),
            "proposal_digest": candidate.proposal_digest,
            "mutations": mutations,
        }

    @staticmethod
    def _replay(completion, *, run_version: int):
        if (
            completion is None
            or completion.result_type is not IdempotencyResultType.MUSIC_DIRECTOR_APPLY
        ):
            raise MusicDirectorApplyError(MusicDirectorApplyErrorCode.STALE_RUN)
        payload = completion.result_payload
        return MusicDirectorApplyResult(
            UUID(payload["run_id"]),
            UUID(payload["candidate_id"]),
            UUID(payload["working_composition_id"]),
            completion.completed_revision,
            run_version,
            UUID(payload["history_entry_id"]),
            True,
        )
