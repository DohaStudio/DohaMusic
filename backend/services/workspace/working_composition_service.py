"""Atomic WorkingComposition, Track, and Clip product mutations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from itertools import pairwise
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    IdempotencyConflictError,
    IdempotencyInProgressError,
    ResourceNotFoundError,
    WorkspaceBootstrapRequiredError,
)
from backend.core.idempotency_completion import (
    IdempotencyCompletionResult,
    IdempotencyResultType,
)
from backend.models.workspace import (
    AssetType,
    CompositionClip,
    CompositionTrack,
    MusicProject,
    WorkingComposition,
)
from backend.repositories.idempotency_repository import (
    IdempotencyClaim,
    IdempotencyRepository,
)
from backend.repositories.workspace import (
    AssetRepository,
    CompositionRepository,
    WorkspaceRepository,
)
from backend.services.workspace.trusted_media_metadata_service import (
    TrustedMediaMetadataError,
    TrustedMediaMetadataErrorCode,
    TrustedMediaMetadataService,
)

IDEMPOTENCY_TTL_HOURS = 24
MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_TRACK_NAME_LENGTH = 200
MICROSECONDS_PER_SECOND = Decimal(1000000)
AUDIO_ASSET_TYPES = frozenset(
    {
        AssetType.MUSIC,
        AssetType.VOCAL,
        AssetType.STEM,
        AssetType.RECORDING,
        AssetType.MIX,
        AssetType.EXPORT,
    }
)


class WorkingCompositionErrorCode(StrEnum):
    WORKING_COMPOSITION_NOT_FOUND = "WORKING_COMPOSITION_NOT_FOUND"
    WORKING_COMPOSITION_ALREADY_EXISTS = "WORKING_COMPOSITION_ALREADY_EXISTS"
    WORKING_COMPOSITION_REVISION_CONFLICT = "WORKING_COMPOSITION_REVISION_CONFLICT"
    TRACK_NOT_FOUND = "TRACK_NOT_FOUND"
    TRACK_NOT_EMPTY = "TRACK_NOT_EMPTY"
    TRACK_ALREADY_ACTIVE = "TRACK_ALREADY_ACTIVE"
    TRACK_RESTORE_ORDER_INVALID = "TRACK_RESTORE_ORDER_INVALID"
    CLIP_NOT_FOUND = "CLIP_NOT_FOUND"
    CLIP_ALREADY_ACTIVE = "CLIP_ALREADY_ACTIVE"
    CLIP_OVERLAP = "CLIP_OVERLAP"
    SPLIT_STRUCTURE_CONFLICT = "SPLIT_STRUCTURE_CONFLICT"
    INVALID_CLIP_RANGE = "INVALID_CLIP_RANGE"
    SOURCE_ASSET_UNAVAILABLE = "SOURCE_ASSET_UNAVAILABLE"
    SOURCE_ARTIFACT_AMBIGUOUS = "SOURCE_ARTIFACT_AMBIGUOUS"
    SOURCE_DURATION_UNAVAILABLE = "SOURCE_DURATION_UNAVAILABLE"
    SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE = "SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE"


_SAFE_ERROR_MESSAGES = {
    WorkingCompositionErrorCode.WORKING_COMPOSITION_NOT_FOUND: (
        "WorkingComposition을 찾을 수 없습니다."
    ),
    WorkingCompositionErrorCode.WORKING_COMPOSITION_ALREADY_EXISTS: (
        "Project에 WorkingComposition이 이미 존재합니다."
    ),
    WorkingCompositionErrorCode.WORKING_COMPOSITION_REVISION_CONFLICT: (
        "WorkingComposition revision이 현재 상태와 일치하지 않습니다."
    ),
    WorkingCompositionErrorCode.TRACK_NOT_FOUND: "Track을 찾을 수 없습니다.",
    WorkingCompositionErrorCode.TRACK_NOT_EMPTY: "활성 Clip이 있는 Track은 삭제할 수 없습니다.",
    WorkingCompositionErrorCode.TRACK_ALREADY_ACTIVE: "Track이 이미 활성 상태입니다.",
    WorkingCompositionErrorCode.TRACK_RESTORE_ORDER_INVALID: (
        "Track 복원 순서가 유효하지 않습니다."
    ),
    WorkingCompositionErrorCode.CLIP_NOT_FOUND: "Clip을 찾을 수 없습니다.",
    WorkingCompositionErrorCode.CLIP_ALREADY_ACTIVE: "Clip이 이미 활성 상태입니다.",
    WorkingCompositionErrorCode.CLIP_OVERLAP: "같은 Track의 활성 Clip은 겹칠 수 없습니다.",
    WorkingCompositionErrorCode.SPLIT_STRUCTURE_CONFLICT: (
        "Split 원본과 child의 canonical geometry가 일치하지 않습니다."
    ),
    WorkingCompositionErrorCode.INVALID_CLIP_RANGE: "Clip 시간 범위가 유효하지 않습니다.",
    WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE: (
        "Clip source AssetVersion을 사용할 수 없습니다."
    ),
    WorkingCompositionErrorCode.SOURCE_ARTIFACT_AMBIGUOUS: (
        "Clip source Artifact를 하나로 결정할 수 없습니다."
    ),
    WorkingCompositionErrorCode.SOURCE_DURATION_UNAVAILABLE: (
        "Clip source의 신뢰할 수 있는 길이가 없습니다."
    ),
    WorkingCompositionErrorCode.SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE: (
        "Snapshot에 checkout 가능한 arrangement가 없습니다."
    ),
}


class WorkingCompositionError(RuntimeError):
    def __init__(self, code: WorkingCompositionErrorCode) -> None:
        super().__init__(_SAFE_ERROR_MESSAGES[code])
        self.code = code


@dataclass(frozen=True, slots=True)
class WorkingCompositionAggregate:
    working_composition: WorkingComposition
    tracks: tuple[CompositionTrack, ...]
    clips: tuple[CompositionClip, ...]
    timeline_duration_us: int


@dataclass(frozen=True, slots=True)
class WorkingMutationResult:
    completed_revision: int
    replayed: bool
    result_type: IdempotencyResultType | None
    identities: Mapping[str, UUID]


class WorkingCompositionService:
    """Own the transaction boundary for canonical composition editing."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_working_composition(
        self, project_id: UUID, *, effective_owner_id: UUID
    ) -> WorkingCompositionAggregate:
        _validate_uuid(project_id, "project_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        with self.session_factory() as session:
            self._require_project_scope(session, project_id, effective_owner_id)
            repository = CompositionRepository(session)
            working = repository.get_project_working_composition(project_id)
            if working is None:
                raise WorkingCompositionError(
                    WorkingCompositionErrorCode.WORKING_COMPOSITION_NOT_FOUND
                )
            return self._load_aggregate(repository, working)

    def initialize(
        self,
        project_id: UUID,
        *,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        _validate_uuid(project_id, "project_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        key = _normalize_idempotency_key(idempotency_key)
        operation = IdempotencyResultType.WORKING_COMPOSITION_INITIALIZE
        fingerprint = _fingerprint(
            effective_owner_id=effective_owner_id,
            project_id=project_id,
            working_composition_id=None,
            operation=operation.value,
            expected_revision=None,
            target_identity=None,
            body={},
        )
        scope = f"working-composition:{effective_owner_id}:{project_id}:initialize"
        try:
            with self.session_factory() as session, session.begin():
                self._require_project_scope(session, project_id, effective_owner_id)
                idempotency = IdempotencyRepository(session)
                claim = _claim_with_result(
                    idempotency,
                    scope=scope,
                    key=key,
                    fingerprint=fingerprint,
                )
                replay = _replay_result(claim, operation)
                if replay is not None:
                    return replay
                repository = CompositionRepository(session)
                if repository.get_project_working_composition(project_id) is not None:
                    raise WorkingCompositionError(
                        WorkingCompositionErrorCode.WORKING_COMPOSITION_ALREADY_EXISTS
                    )
                working = repository.add_working_composition(
                    WorkingComposition(
                        project_id=project_id,
                        base_composition_snapshot_id=None,
                        mix_settings={},
                        revision=0,
                    )
                )
                result = _complete_result(
                    idempotency,
                    claim,
                    completed_revision=0,
                    result_type=operation,
                    payload={"working_composition_id": working.working_composition_id},
                    resource_type="working_composition",
                    resource_id=working.working_composition_id,
                    response_status=201,
                )
            return result
        except IntegrityError:
            if self._project_has_working_composition(project_id, effective_owner_id):
                raise WorkingCompositionError(
                    WorkingCompositionErrorCode.WORKING_COMPOSITION_ALREADY_EXISTS
                ) from None
            raise

    def checkout(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        composition_snapshot_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(composition_snapshot_id, "composition_snapshot_id")
        operation = IdempotencyResultType.WORKING_COMPOSITION_CHECKOUT
        body = {"composition_snapshot_id": str(composition_snapshot_id)}
        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=composition_snapshot_id,
            body=body,
            mutate=lambda repository, _session, working: self._checkout_rows(
                repository,
                working,
                composition_snapshot_id=composition_snapshot_id,
            ),
            payload=lambda _identity: {
                "working_composition_id": working_composition_id,
                "base_composition_snapshot_id": composition_snapshot_id,
            },
            resource_type="working_composition",
            resource_id=lambda _identity: working_composition_id,
            response_status=200,
        )

    def create_track(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        name: str,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        track_name = _normalize_track_name(name)
        operation = IdempotencyResultType.TRACK_CREATE

        def mutate(
            repository: CompositionRepository,
            _session: Session,
            working: WorkingComposition,
        ) -> UUID:
            track = repository.add_composition_track(
                CompositionTrack(
                    working_composition_id=working.working_composition_id,
                    track_type="audio",
                    name=track_name,
                    track_order=len(
                        repository.list_active_composition_tracks(working.working_composition_id)
                    ),
                )
            )
            return track.track_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=None,
            body={"name": track_name},
            mutate=mutate,
            payload=lambda track_id: {"track_id": track_id},
            resource_type="composition_track",
            resource_id=lambda track_id: track_id,
            response_status=201,
        )

    def rename_track(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        track_id: UUID,
        name: str,
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(track_id, "track_id")
        track_name = _normalize_track_name(name)

        def mutate(repository: CompositionRepository, working: WorkingComposition) -> UUID:
            track = self._require_track(repository, working, track_id)
            track.name = track_name
            repository.flush()
            return track.track_id

        return self._run_absolute_mutation(**normalized, mutate=mutate)

    def reorder_tracks(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        ordered_track_ids: Sequence[UUID],
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        order = tuple(ordered_track_ids)
        if not order or len(set(order)) != len(order):
            raise ApplicationValidationError(
                "ordered_track_ids는 중복 없는 전체 active Track 목록이어야 합니다."
            )
        for track_id in order:
            _validate_uuid(track_id, "ordered_track_ids")

        def mutate(repository: CompositionRepository, working: WorkingComposition) -> UUID:
            try:
                repository.reorder_active_composition_tracks(working.working_composition_id, order)
            except ValueError:
                raise ApplicationValidationError(
                    "ordered_track_ids는 전체 active Track과 정확히 일치해야 합니다."
                ) from None
            return working.working_composition_id

        return self._run_absolute_mutation(**normalized, mutate=mutate)

    def delete_track(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        track_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(track_id, "track_id")
        operation = IdempotencyResultType.TRACK_DELETE

        def mutate(
            repository: CompositionRepository,
            _session: Session,
            working: WorkingComposition,
        ) -> UUID:
            track = self._require_track(repository, working, track_id)
            if repository.count_active_composition_clips(
                working_composition_id=working.working_composition_id,
                track_id=track.track_id,
            ):
                raise WorkingCompositionError(WorkingCompositionErrorCode.TRACK_NOT_EMPTY)
            repository.tombstone_composition_track(track)
            return track.track_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=track_id,
            body={},
            mutate=mutate,
            payload=lambda identity: {"track_id": identity},
            resource_type="composition_track",
            resource_id=lambda identity: identity,
            response_status=200,
        )

    def restore_track(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        track_id: UUID,
        target_track_order: int,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(track_id, "track_id")
        if type(target_track_order) is not int or target_track_order < 0:
            raise WorkingCompositionError(WorkingCompositionErrorCode.TRACK_RESTORE_ORDER_INVALID)
        operation = IdempotencyResultType.TRACK_RESTORE

        def mutate(
            repository: CompositionRepository,
            _session: Session,
            working: WorkingComposition,
        ) -> UUID:
            track = self._require_track_any(repository, working, track_id)
            if track.deleted_at is None:
                raise WorkingCompositionError(WorkingCompositionErrorCode.TRACK_ALREADY_ACTIVE)
            try:
                repository.restore_composition_track(track, target_track_order=target_track_order)
            except ValueError as error:
                code = (
                    WorkingCompositionErrorCode.TRACK_ALREADY_ACTIVE
                    if str(error) == "TRACK_ALREADY_ACTIVE"
                    else WorkingCompositionErrorCode.TRACK_RESTORE_ORDER_INVALID
                )
                raise WorkingCompositionError(code) from None
            return track.track_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=track_id,
            body={"target_track_order": target_track_order},
            mutate=mutate,
            payload=lambda identity: {"track_id": identity},
            resource_type="composition_track",
            resource_id=lambda identity: identity,
            response_status=200,
        )

    def create_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        track_id: UUID,
        source_asset_version_id: UUID,
        timeline_start: object,
        source_in: object,
        source_out: object,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(track_id, "track_id")
        _validate_uuid(source_asset_version_id, "source_asset_version_id")
        start_us = _seconds_to_microseconds(timeline_start, "timeline_start")
        source_in_us = _seconds_to_microseconds(source_in, "source_in")
        source_out_us = _seconds_to_microseconds(source_out, "source_out")
        operation = IdempotencyResultType.CLIP_CREATE

        def mutate(
            repository: CompositionRepository,
            session: Session,
            working: WorkingComposition,
        ) -> UUID:
            self._require_track(repository, working, track_id)
            source_duration = self._resolve_source_duration(
                session,
                project_id=project_id,
                workspace_id=self._project_workspace_id(session, project_id, effective_owner_id),
                effective_owner_id=effective_owner_id,
                asset_version_id=source_asset_version_id,
            )
            _validate_clip_range(
                timeline_start=start_us,
                source_in=source_in_us,
                source_out=source_out_us,
                source_duration=source_duration,
            )
            clip = CompositionClip(
                working_composition_id=working.working_composition_id,
                track_id=track_id,
                source_asset_version_id=source_asset_version_id,
                timeline_start=start_us,
                source_in=source_in_us,
                source_out=source_out_us,
                source_duration=source_duration,
                split_from_clip_id=None,
            )
            try:
                repository.add_composition_clip(clip)
            except ValueError:
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP) from None
            return clip.clip_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=track_id,
            body={
                "source_asset_version_id": str(source_asset_version_id),
                "timeline_start_us": start_us,
                "source_in_us": source_in_us,
                "source_out_us": source_out_us,
            },
            mutate=mutate,
            payload=lambda identity: {"clip_id": identity},
            resource_type="composition_clip",
            resource_id=lambda identity: identity,
            response_status=201,
        )

    def move_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        timeline_start: object,
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> WorkingMutationResult:
        start_us = _seconds_to_microseconds(timeline_start, "timeline_start")
        return self._mutate_clip_absolute(
            project_id=project_id,
            working_composition_id=working_composition_id,
            clip_id=clip_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
            changes=lambda clip: {"timeline_start": start_us},
        )

    def trim_clip_start(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        timeline_start: object,
        source_in: object,
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> WorkingMutationResult:
        start_us = _seconds_to_microseconds(timeline_start, "timeline_start")
        source_in_us = _seconds_to_microseconds(source_in, "source_in")
        return self._mutate_clip_absolute(
            project_id=project_id,
            working_composition_id=working_composition_id,
            clip_id=clip_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
            changes=lambda clip: {
                "timeline_start": start_us,
                "source_in": source_in_us,
            },
        )

    def trim_clip_end(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        source_out: object,
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> WorkingMutationResult:
        source_out_us = _seconds_to_microseconds(source_out, "source_out")
        return self._mutate_clip_absolute(
            project_id=project_id,
            working_composition_id=working_composition_id,
            clip_id=clip_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
            changes=lambda clip: {"source_out": source_out_us},
        )

    def split_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        split_at: object,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(clip_id, "clip_id")
        split_at_us = _seconds_to_microseconds(split_at, "split_at")
        operation = IdempotencyResultType.CLIP_SPLIT

        def mutate(
            repository: CompositionRepository,
            _session: Session,
            working: WorkingComposition,
        ) -> tuple[UUID, UUID, UUID]:
            original = self._require_clip(repository, working, clip_id)
            timeline_end = original.timeline_start + (original.source_out - original.source_in)
            if not original.timeline_start < split_at_us < timeline_end:
                raise WorkingCompositionError(WorkingCompositionErrorCode.INVALID_CLIP_RANGE)
            source_split = original.source_in + (split_at_us - original.timeline_start)
            repository.tombstone_composition_clip(original)
            left = CompositionClip(
                working_composition_id=working.working_composition_id,
                track_id=original.track_id,
                source_asset_version_id=original.source_asset_version_id,
                timeline_start=original.timeline_start,
                source_in=original.source_in,
                source_out=source_split,
                source_duration=original.source_duration,
                split_from_clip_id=original.clip_id,
            )
            right = CompositionClip(
                working_composition_id=working.working_composition_id,
                track_id=original.track_id,
                source_asset_version_id=original.source_asset_version_id,
                timeline_start=split_at_us,
                source_in=source_split,
                source_out=original.source_out,
                source_duration=original.source_duration,
                split_from_clip_id=original.clip_id,
            )
            try:
                repository.add_composition_clip(left)
                repository.add_composition_clip(right)
            except ValueError:
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP) from None
            return original.clip_id, left.clip_id, right.clip_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=clip_id,
            body={"split_at_us": split_at_us},
            mutate=mutate,
            payload=lambda identities: {
                "original_clip_id": identities[0],
                "left_clip_id": identities[1],
                "right_clip_id": identities[2],
            },
            resource_type="composition_clip_split",
            resource_id=lambda identities: identities[0],
            response_status=200,
        )

    def delete_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(clip_id, "clip_id")
        operation = IdempotencyResultType.CLIP_DELETE

        def mutate(
            repository: CompositionRepository,
            _session: Session,
            working: WorkingComposition,
        ) -> UUID:
            clip = self._require_clip(repository, working, clip_id)
            repository.tombstone_composition_clip(clip)
            return clip.clip_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=clip_id,
            body={},
            mutate=mutate,
            payload=lambda identity: {"clip_id": identity},
            resource_type="composition_clip",
            resource_id=lambda identity: identity,
            response_status=200,
        )

    def restore_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(clip_id, "clip_id")
        operation = IdempotencyResultType.CLIP_RESTORE

        def mutate(
            repository: CompositionRepository,
            session: Session,
            working: WorkingComposition,
        ) -> UUID:
            clip = self._require_clip_any(repository, working, clip_id)
            if clip.deleted_at is None:
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_ALREADY_ACTIVE)
            self._require_track(repository, working, clip.track_id)
            self._validate_restore_source(
                session,
                project_id=project_id,
                effective_owner_id=effective_owner_id,
                clip=clip,
            )
            timeline_end = clip.timeline_start + clip.source_out - clip.source_in
            if repository.active_clip_overlap_exists(
                working_composition_id=working.working_composition_id,
                track_id=clip.track_id,
                timeline_start=clip.timeline_start,
                timeline_end=timeline_end,
            ):
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP)
            repository.restore_composition_clip(clip)
            return clip.clip_id

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=clip_id,
            body={},
            mutate=mutate,
            payload=lambda identity: {"clip_id": identity},
            resource_type="composition_clip",
            resource_id=lambda identity: identity,
            response_status=200,
        )

    def unsplit_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        original_clip_id: UUID,
        left_clip_id: UUID,
        right_clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        return self._toggle_split(
            project_id=project_id,
            working_composition_id=working_composition_id,
            original_clip_id=original_clip_id,
            left_clip_id=left_clip_id,
            right_clip_id=right_clip_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
            idempotency_key=idempotency_key,
            operation=IdempotencyResultType.CLIP_UNSPLIT,
            activate_original=True,
        )

    def resplit_clip(
        self,
        project_id: UUID,
        *,
        working_composition_id: UUID,
        original_clip_id: UUID,
        left_clip_id: UUID,
        right_clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
    ) -> WorkingMutationResult:
        return self._toggle_split(
            project_id=project_id,
            working_composition_id=working_composition_id,
            original_clip_id=original_clip_id,
            left_clip_id=left_clip_id,
            right_clip_id=right_clip_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
            idempotency_key=idempotency_key,
            operation=IdempotencyResultType.CLIP_RESPLIT,
            activate_original=False,
        )

    def _toggle_split(
        self,
        *,
        project_id: UUID,
        working_composition_id: UUID,
        original_clip_id: UUID,
        left_clip_id: UUID,
        right_clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
        operation: IdempotencyResultType,
        activate_original: bool,
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        identities = (original_clip_id, left_clip_id, right_clip_id)
        for identity in identities:
            _validate_uuid(identity, "clip_id")
        if len(set(identities)) != 3:
            raise WorkingCompositionError(WorkingCompositionErrorCode.SPLIT_STRUCTURE_CONFLICT)

        def mutate(
            repository: CompositionRepository,
            session: Session,
            working: WorkingComposition,
        ) -> tuple[UUID, UUID, UUID]:
            original = self._require_clip_any(repository, working, original_clip_id)
            left = self._require_clip_any(repository, working, left_clip_id)
            right = self._require_clip_any(repository, working, right_clip_id)
            if activate_original:
                valid_state = (
                    original.deleted_at is not None
                    and left.deleted_at is None
                    and right.deleted_at is None
                )
            else:
                valid_state = (
                    original.deleted_at is None
                    and left.deleted_at is not None
                    and right.deleted_at is not None
                )
            if not valid_state or not _split_geometry_matches(original, left, right):
                raise WorkingCompositionError(WorkingCompositionErrorCode.SPLIT_STRUCTURE_CONFLICT)
            self._require_track(repository, working, original.track_id)
            self._validate_restore_source(
                session,
                project_id=project_id,
                effective_owner_id=effective_owner_id,
                clip=original,
            )

            if activate_original:
                repository.tombstone_composition_clip(left)
                repository.tombstone_composition_clip(right)
                original_end = original.timeline_start + original.source_out - original.source_in
                if repository.active_clip_overlap_exists(
                    working_composition_id=working.working_composition_id,
                    track_id=original.track_id,
                    timeline_start=original.timeline_start,
                    timeline_end=original_end,
                ):
                    raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP)
                repository.restore_composition_clip(original)
            else:
                repository.tombstone_composition_clip(original)
                for child in (left, right):
                    child_end = child.timeline_start + child.source_out - child.source_in
                    if repository.active_clip_overlap_exists(
                        working_composition_id=working.working_composition_id,
                        track_id=child.track_id,
                        timeline_start=child.timeline_start,
                        timeline_end=child_end,
                    ):
                        raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP)
                repository.restore_composition_clip(left)
                repository.restore_composition_clip(right)
            return identities

        return self._run_idempotent_mutation(
            **normalized,
            idempotency_key=idempotency_key,
            operation=operation,
            target_identity=original_clip_id,
            body={
                "left_clip_id": str(left_clip_id),
                "right_clip_id": str(right_clip_id),
            },
            mutate=mutate,
            payload=lambda value: {
                "original_clip_id": value[0],
                "left_clip_id": value[1],
                "right_clip_id": value[2],
            },
            resource_type="composition_clip_split",
            resource_id=lambda value: value[0],
            response_status=200,
        )

    def _mutate_clip_absolute(
        self,
        *,
        project_id: UUID,
        working_composition_id: UUID,
        clip_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        changes: Callable[[CompositionClip], dict[str, int]],
    ) -> WorkingMutationResult:
        normalized = self._normalize_mutation(
            project_id=project_id,
            working_composition_id=working_composition_id,
            expected_revision=expected_revision,
            effective_owner_id=effective_owner_id,
        )
        _validate_uuid(clip_id, "clip_id")

        def mutate(repository: CompositionRepository, working: WorkingComposition) -> UUID:
            clip = self._require_clip(repository, working, clip_id)
            values = changes(clip)
            timeline_start = values.get("timeline_start", clip.timeline_start)
            source_in = values.get("source_in", clip.source_in)
            source_out = values.get("source_out", clip.source_out)
            _validate_clip_range(
                timeline_start=timeline_start,
                source_in=source_in,
                source_out=source_out,
                source_duration=clip.source_duration,
            )
            timeline_end = timeline_start + source_out - source_in
            if repository.active_clip_overlap_exists(
                working_composition_id=working.working_composition_id,
                track_id=clip.track_id,
                timeline_start=timeline_start,
                timeline_end=timeline_end,
                exclude_clip_id=clip.clip_id,
            ):
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP)
            for field_name, value in values.items():
                setattr(clip, field_name, value)
            repository.flush()
            return clip.clip_id

        return self._run_absolute_mutation(**normalized, mutate=mutate)

    def _run_absolute_mutation(
        self,
        *,
        project_id: UUID,
        working_composition_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        mutate: Callable[[CompositionRepository, WorkingComposition], UUID],
    ) -> WorkingMutationResult:
        with self.session_factory() as session, session.begin():
            self._require_project_scope(session, project_id, effective_owner_id)
            repository = CompositionRepository(session)
            working = self._require_working(repository, project_id, working_composition_id)
            _require_expected_revision(working, expected_revision)
            identity = mutate(repository, working)
            revision = self._increment_revision(
                repository, working_composition_id, expected_revision
            )
            return WorkingMutationResult(
                completed_revision=revision,
                replayed=False,
                result_type=None,
                identities={"resource_id": identity},
            )

    def _run_idempotent_mutation(
        self,
        *,
        project_id: UUID,
        working_composition_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
        idempotency_key: str,
        operation: IdempotencyResultType,
        target_identity: UUID | None,
        body: Mapping[str, object],
        mutate: Callable[[CompositionRepository, Session, WorkingComposition], object],
        payload: Callable[[object], Mapping[str, UUID]],
        resource_type: str,
        resource_id: Callable[[object], UUID],
        response_status: int,
    ) -> WorkingMutationResult:
        key = _normalize_idempotency_key(idempotency_key)
        fingerprint = _fingerprint(
            effective_owner_id=effective_owner_id,
            project_id=project_id,
            working_composition_id=working_composition_id,
            operation=operation.value,
            expected_revision=expected_revision,
            target_identity=target_identity,
            body=body,
        )
        scope = (
            f"working-composition:{effective_owner_id}:{project_id}:"
            f"{working_composition_id}:{operation.value}"
        )
        with self.session_factory() as session, session.begin():
            self._require_project_scope(session, project_id, effective_owner_id)
            idempotency = IdempotencyRepository(session)
            claim = _claim_with_result(
                idempotency,
                scope=scope,
                key=key,
                fingerprint=fingerprint,
            )
            replay = _replay_result(claim, operation)
            if replay is not None:
                return replay
            repository = CompositionRepository(session)
            working = self._require_working(repository, project_id, working_composition_id)
            _require_expected_revision(working, expected_revision)
            identity = mutate(repository, session, working)
            revision = self._increment_revision(
                repository, working_composition_id, expected_revision
            )
            result_payload = payload(identity)
            return _complete_result(
                idempotency,
                claim,
                completed_revision=revision,
                result_type=operation,
                payload=result_payload,
                resource_type=resource_type,
                resource_id=resource_id(identity),
                response_status=response_status,
            )

    def _checkout_rows(
        self,
        repository: CompositionRepository,
        working: WorkingComposition,
        *,
        composition_snapshot_id: UUID,
    ) -> UUID:
        snapshot = repository.get_project_snapshot(working.project_id, composition_snapshot_id)
        if snapshot is None:
            raise ResourceNotFoundError("CompositionSnapshot")
        snapshot_tracks = repository.list_snapshot_tracks(composition_snapshot_id)
        if not snapshot_tracks:
            raise WorkingCompositionError(
                WorkingCompositionErrorCode.SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE
            )
        snapshot_clips = repository.list_snapshot_clips_for_snapshot(composition_snapshot_id)
        self._validate_checkout_overlap(snapshot_tracks, snapshot_clips)

        for clip in repository.list_working_composition_clips(working.working_composition_id):
            repository.tombstone_composition_clip(clip)
        for track in repository.list_active_composition_tracks(working.working_composition_id):
            repository.tombstone_composition_track(track)

        track_by_snapshot_id = {}
        for source in snapshot_tracks:
            target = repository.get_composition_track(
                working.working_composition_id,
                source.canonical_track_id,
                include_deleted=True,
            )
            if target is None:
                target = CompositionTrack(
                    track_id=source.canonical_track_id,
                    working_composition_id=working.working_composition_id,
                    track_type=source.track_type,
                    name=source.name,
                    track_order=source.track_order,
                )
                repository.add_composition_track(target)
            else:
                target.track_type = source.track_type
                target.name = source.name
                target.track_order = source.track_order
                target.deleted_at = None
                repository.flush()
            track_by_snapshot_id[source.snapshot_track_id] = target.track_id

        for source in snapshot_clips:
            target = repository.get_composition_clip(
                working.working_composition_id,
                source.canonical_clip_id,
                include_deleted=True,
            )
            values = {
                "track_id": track_by_snapshot_id[source.snapshot_track_id],
                "source_asset_version_id": source.source_asset_version_id,
                "timeline_start": source.timeline_start,
                "source_in": source.source_in,
                "source_out": source.source_out,
                "source_duration": source.source_duration,
                "split_from_clip_id": source.split_from_clip_id,
            }
            if target is None:
                repository.add_composition_clip(
                    CompositionClip(
                        clip_id=source.canonical_clip_id,
                        working_composition_id=working.working_composition_id,
                        **values,
                    )
                )
            else:
                for field_name, value in values.items():
                    setattr(target, field_name, value)
                target.deleted_at = None
                repository.flush()
        working.base_composition_snapshot_id = composition_snapshot_id
        repository.flush()
        return working.working_composition_id

    @staticmethod
    def _validate_checkout_overlap(snapshot_tracks: Sequence, snapshot_clips: Sequence) -> None:
        known_tracks = {track.snapshot_track_id for track in snapshot_tracks}
        by_track: dict[UUID, list[tuple[int, int]]] = {}
        for clip in snapshot_clips:
            if clip.snapshot_track_id not in known_tracks:
                raise WorkingCompositionError(
                    WorkingCompositionErrorCode.SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE
                )
            _validate_clip_range(
                timeline_start=clip.timeline_start,
                source_in=clip.source_in,
                source_out=clip.source_out,
                source_duration=clip.source_duration,
            )
            interval = (
                clip.timeline_start,
                clip.timeline_start + clip.source_out - clip.source_in,
            )
            by_track.setdefault(clip.snapshot_track_id, []).append(interval)
        for intervals in by_track.values():
            ordered = sorted(intervals)
            if any(left[1] > right[0] for left, right in pairwise(ordered)):
                raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_OVERLAP)

    def _resolve_source_duration(
        self,
        session: Session,
        *,
        project_id: UUID,
        workspace_id: UUID,
        effective_owner_id: UUID,
        asset_version_id: UUID,
    ) -> int:
        assets = AssetRepository(session)
        version = assets.get_asset_version(asset_version_id)
        if version is None:
            raise WorkingCompositionError(WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE)
        asset = assets.get_asset(version.asset_id)
        if (
            asset is None
            or asset.owner_id != effective_owner_id
            or asset.workspace_id not in {None, workspace_id}
            or asset.deleted_at is not None
            or asset.lifecycle_status != "active"
            or asset.asset_type not in AUDIO_ASSET_TYPES
            or not WorkspaceRepository(session).project_asset_exists(project_id, asset.asset_id)
        ):
            raise WorkingCompositionError(WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE)
        try:
            return (
                TrustedMediaMetadataService(assets)
                .resolve_clip_source(asset_version_id)
                .duration_us
            )
        except TrustedMediaMetadataError as error:
            mapping = {
                TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_NOT_FOUND: (
                    WorkingCompositionErrorCode.SOURCE_ASSET_UNAVAILABLE
                ),
                TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_AMBIGUOUS: (
                    WorkingCompositionErrorCode.SOURCE_ARTIFACT_AMBIGUOUS
                ),
                TrustedMediaMetadataErrorCode.SOURCE_DURATION_UNAVAILABLE: (
                    WorkingCompositionErrorCode.SOURCE_DURATION_UNAVAILABLE
                ),
            }
            raise WorkingCompositionError(mapping[error.code]) from None

    def _validate_restore_source(
        self,
        session: Session,
        *,
        project_id: UUID,
        effective_owner_id: UUID,
        clip: CompositionClip,
    ) -> None:
        """Recheck current eligibility without replacing frozen Clip geometry."""

        self._resolve_source_duration(
            session,
            project_id=project_id,
            workspace_id=self._project_workspace_id(session, project_id, effective_owner_id),
            effective_owner_id=effective_owner_id,
            asset_version_id=clip.source_asset_version_id,
        )

    def _normalize_mutation(
        self,
        *,
        project_id: UUID,
        working_composition_id: UUID,
        expected_revision: int,
        effective_owner_id: UUID,
    ) -> dict[str, object]:
        _validate_uuid(project_id, "project_id")
        _validate_uuid(working_composition_id, "working_composition_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        _validate_expected_revision(expected_revision)
        return {
            "project_id": project_id,
            "working_composition_id": working_composition_id,
            "expected_revision": expected_revision,
            "effective_owner_id": effective_owner_id,
        }

    @staticmethod
    def _require_working(
        repository: CompositionRepository,
        project_id: UUID,
        working_composition_id: UUID,
    ) -> WorkingComposition:
        working = repository.get_working_composition(working_composition_id)
        if working is None or working.project_id != project_id:
            raise WorkingCompositionError(WorkingCompositionErrorCode.WORKING_COMPOSITION_NOT_FOUND)
        return working

    @staticmethod
    def _require_track(
        repository: CompositionRepository,
        working: WorkingComposition,
        track_id: UUID,
    ) -> CompositionTrack:
        track = repository.get_composition_track(working.working_composition_id, track_id)
        if track is None:
            raise WorkingCompositionError(WorkingCompositionErrorCode.TRACK_NOT_FOUND)
        return track

    @staticmethod
    def _require_track_any(
        repository: CompositionRepository,
        working: WorkingComposition,
        track_id: UUID,
    ) -> CompositionTrack:
        track = repository.get_composition_track(
            working.working_composition_id, track_id, include_deleted=True
        )
        if track is None:
            raise WorkingCompositionError(WorkingCompositionErrorCode.TRACK_NOT_FOUND)
        return track

    @staticmethod
    def _require_clip(
        repository: CompositionRepository,
        working: WorkingComposition,
        clip_id: UUID,
    ) -> CompositionClip:
        clip = repository.get_composition_clip(working.working_composition_id, clip_id)
        if clip is None:
            raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_NOT_FOUND)
        return clip

    @staticmethod
    def _require_clip_any(
        repository: CompositionRepository,
        working: WorkingComposition,
        clip_id: UUID,
    ) -> CompositionClip:
        clip = repository.get_composition_clip(
            working.working_composition_id, clip_id, include_deleted=True
        )
        if clip is None:
            raise WorkingCompositionError(WorkingCompositionErrorCode.CLIP_NOT_FOUND)
        return clip

    @staticmethod
    def _increment_revision(
        repository: CompositionRepository,
        working_composition_id: UUID,
        expected_revision: int,
    ) -> int:
        revision = repository.increment_working_revision(
            working_composition_id, expected_revision=expected_revision
        )
        if revision is None:
            raise WorkingCompositionError(
                WorkingCompositionErrorCode.WORKING_COMPOSITION_REVISION_CONFLICT
            )
        return revision

    @staticmethod
    def _require_project_scope(
        session: Session,
        project_id: UUID,
        effective_owner_id: UUID,
    ) -> MusicProject:
        repository = WorkspaceRepository(session)
        if not repository.list_workspaces(owner_id=effective_owner_id, limit=1):
            raise WorkspaceBootstrapRequiredError()
        project = repository.get_project(project_id)
        if project is None or project.lifecycle_status != "active":
            raise ResourceNotFoundError("MusicProject")
        workspace = repository.get_workspace_for_owner(project.workspace_id, effective_owner_id)
        if workspace is None or workspace.lifecycle_status != "active":
            raise ResourceNotFoundError("MusicProject")
        return project

    def _project_workspace_id(
        self, session: Session, project_id: UUID, effective_owner_id: UUID
    ) -> UUID:
        return self._require_project_scope(session, project_id, effective_owner_id).workspace_id

    def _project_has_working_composition(self, project_id: UUID, effective_owner_id: UUID) -> bool:
        with self.session_factory() as session:
            self._require_project_scope(session, project_id, effective_owner_id)
            return (
                CompositionRepository(session).get_project_working_composition(project_id)
                is not None
            )

    @staticmethod
    def _load_aggregate(
        repository: CompositionRepository, working: WorkingComposition
    ) -> WorkingCompositionAggregate:
        tracks = repository.list_active_composition_tracks(working.working_composition_id)
        clips = repository.list_working_composition_clips(working.working_composition_id)
        duration = max(
            (clip.timeline_start + clip.source_out - clip.source_in for clip in clips),
            default=0,
        )
        return WorkingCompositionAggregate(
            working_composition=working,
            tracks=tuple(tracks),
            clips=tuple(clips),
            timeline_duration_us=duration,
        )


def _claim_with_result(
    repository: IdempotencyRepository,
    *,
    scope: str,
    key: str,
    fingerprint: str,
) -> IdempotencyClaim:
    try:
        return repository.claim_with_result(
            scope=scope,
            key=key,
            fingerprint=fingerprint,
            now=datetime.now(UTC),
            ttl_hours=IDEMPOTENCY_TTL_HOURS,
        )
    except ValueError as error:
        if str(error) == "IDEMPOTENCY_CONFLICT":
            raise IdempotencyConflictError() from None
        if str(error) == "IDEMPOTENCY_IN_PROGRESS":
            raise IdempotencyInProgressError() from None
        raise IdempotencyConflictError() from None


def _replay_result(
    claim: IdempotencyClaim,
    expected_type: IdempotencyResultType,
) -> WorkingMutationResult | None:
    if not claim.replayed:
        return None
    result = claim.completion_result
    if result is None or result.result_type is not expected_type:
        raise IdempotencyConflictError()
    return WorkingMutationResult(
        completed_revision=result.completed_revision,
        replayed=True,
        result_type=result.result_type,
        identities={key: UUID(value) for key, value in result.result_payload.items()},
    )


def _complete_result(
    repository: IdempotencyRepository,
    claim: IdempotencyClaim,
    *,
    completed_revision: int,
    result_type: IdempotencyResultType,
    payload: Mapping[str, UUID],
    resource_type: str,
    resource_id: UUID,
    response_status: int,
) -> WorkingMutationResult:
    completion = IdempotencyCompletionResult.create(
        completed_revision=completed_revision,
        result_type=result_type,
        result_payload={key: str(value) for key, value in payload.items()},
    )
    repository.complete_with_result(
        claim.record,
        resource_type=resource_type,
        resource_id=str(resource_id),
        response_status=response_status,
        completion_result=completion,
    )
    return WorkingMutationResult(
        completed_revision=completed_revision,
        replayed=False,
        result_type=result_type,
        identities=dict(payload),
    )


def _fingerprint(
    *,
    effective_owner_id: UUID,
    project_id: UUID,
    working_composition_id: UUID | None,
    operation: str,
    expected_revision: int | None,
    target_identity: UUID | None,
    body: Mapping[str, object],
) -> str:
    canonical = json.dumps(
        {
            "body": dict(body),
            "effective_owner_id": str(effective_owner_id),
            "expected_revision": expected_revision,
            "operation": operation,
            "project_id": str(project_id),
            "target_identity": (str(target_identity) if target_identity is not None else None),
            "working_composition_id": (
                str(working_composition_id) if working_composition_id is not None else None
            ),
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_idempotency_key(value: object) -> str:
    if not isinstance(value, str):
        raise ApplicationValidationError("Idempotency-Key가 필요합니다.")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ApplicationValidationError("Idempotency-Key가 필요합니다.")
    return normalized


def _normalize_track_name(value: object) -> str:
    if not isinstance(value, str):
        raise ApplicationValidationError("Track name은 문자열이어야 합니다.")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_TRACK_NAME_LENGTH:
        raise ApplicationValidationError(
            f"Track name은 1자 이상 {MAX_TRACK_NAME_LENGTH}자 이하여야 합니다."
        )
    return normalized


def _validate_uuid(value: object, field_name: str) -> None:
    if type(value) is not UUID:
        raise ApplicationValidationError(f"{field_name} 형식이 유효하지 않습니다.")


def _validate_expected_revision(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ApplicationValidationError("expected_revision은 0 이상의 정수여야 합니다.")


def _require_expected_revision(working: WorkingComposition, expected_revision: int) -> None:
    if working.revision != expected_revision:
        raise WorkingCompositionError(
            WorkingCompositionErrorCode.WORKING_COMPOSITION_REVISION_CONFLICT
        )


def _seconds_to_microseconds(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ApplicationValidationError(f"{field_name} 값이 유효하지 않습니다.")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ApplicationValidationError(f"{field_name} 값이 유효하지 않습니다.") from None
    if not decimal.is_finite():
        raise ApplicationValidationError(f"{field_name} 값이 유효하지 않습니다.")
    return int((decimal * MICROSECONDS_PER_SECOND).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _validate_clip_range(
    *,
    timeline_start: int,
    source_in: int,
    source_out: int,
    source_duration: int,
) -> None:
    if not (
        timeline_start >= 0
        and source_in >= 0
        and source_out > source_in
        and source_out <= source_duration
    ):
        raise WorkingCompositionError(WorkingCompositionErrorCode.INVALID_CLIP_RANGE)


def _split_geometry_matches(
    original: CompositionClip,
    left: CompositionClip,
    right: CompositionClip,
) -> bool:
    original_end = original.timeline_start + original.source_out - original.source_in
    left_end = left.timeline_start + left.source_out - left.source_in
    right_end = right.timeline_start + right.source_out - right.source_in
    return (
        left.working_composition_id == original.working_composition_id
        and right.working_composition_id == original.working_composition_id
        and left.track_id == original.track_id
        and right.track_id == original.track_id
        and left.split_from_clip_id == original.clip_id
        and right.split_from_clip_id == original.clip_id
        and left.source_asset_version_id == original.source_asset_version_id
        and right.source_asset_version_id == original.source_asset_version_id
        and left.source_duration == original.source_duration
        and right.source_duration == original.source_duration
        and left.source_in == original.source_in
        and left.source_out == right.source_in
        and right.source_out == original.source_out
        and left.timeline_start == original.timeline_start
        and left_end == right.timeline_start
        and right_end == original_end
    )
