"""Composition Snapshot과 Processing aggregate persistence operations."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.orm import Session

from backend.models.workspace.asset import Artifact, Asset, AssetVersion
from backend.models.workspace.composition import (
    CompositionClip,
    CompositionSnapshot,
    CompositionSnapshotClip,
    CompositionSnapshotTrack,
    CompositionTrack,
    ProcessingChain,
    ProcessingStep,
    ProjectCompositionSelection,
    SnapshotItem,
    WorkingComposition,
)
from backend.models.workspace.mixins import utc_now
from backend.models.workspace.workspace import MusicProject


@dataclass(frozen=True, slots=True)
class ProjectCompositionTransitionState:
    """한 Project의 Snapshot/selection 전환 inventory."""

    project_id: UUID
    has_snapshots: bool
    selected_snapshot_id: UUID | None
    selected_snapshot_project_id: UUID | None


class CompositionRepository:
    """불변 Composition aggregate를 commit 없이 현재 transaction에 추가한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_working_composition(
        self, working_composition: WorkingComposition
    ) -> WorkingComposition:
        _validate_mix_settings(working_composition.mix_settings)
        self.session.add(working_composition)
        self.session.flush()
        return working_composition

    def get_working_composition(self, working_composition_id: UUID) -> WorkingComposition | None:
        return self.session.get(WorkingComposition, working_composition_id)

    def get_project_working_composition(self, project_id: UUID) -> WorkingComposition | None:
        return self.session.scalar(
            select(WorkingComposition).where(WorkingComposition.project_id == project_id)
        )

    def flush(self) -> None:
        """Expose transaction-local constraint validation without committing."""

        self.session.flush()

    def increment_working_revision(
        self, working_composition_id: UUID, *, expected_revision: int
    ) -> int | None:
        """Expected revision이 일치할 때만 정확히 1 증가시킨다."""

        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision은 0 이상의 정수여야 합니다.")
        statement = (
            update(WorkingComposition)
            .where(
                WorkingComposition.working_composition_id == working_composition_id,
                WorkingComposition.revision == expected_revision,
            )
            .values(
                revision=WorkingComposition.revision + 1,
                updated_at=utc_now(),
            )
            .returning(WorkingComposition.revision)
        )
        return self.session.scalar(statement)

    def add_composition_track(self, track: CompositionTrack) -> CompositionTrack:
        self.session.add(track)
        self.session.flush()
        return track

    def get_composition_track(
        self,
        working_composition_id: UUID,
        track_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> CompositionTrack | None:
        statement = select(CompositionTrack).where(
            CompositionTrack.working_composition_id == working_composition_id,
            CompositionTrack.track_id == track_id,
        )
        if not include_deleted:
            statement = statement.where(CompositionTrack.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_active_composition_tracks(
        self, working_composition_id: UUID
    ) -> list[CompositionTrack]:
        statement = (
            select(CompositionTrack)
            .where(
                CompositionTrack.working_composition_id == working_composition_id,
                CompositionTrack.deleted_at.is_(None),
            )
            .order_by(CompositionTrack.track_order, CompositionTrack.track_id)
        )
        return list(self.session.scalars(statement))

    def reorder_active_composition_tracks(
        self,
        working_composition_id: UUID,
        ordered_track_ids: Sequence[UUID],
    ) -> None:
        """Reassign the full active order without transient unique collisions."""

        tracks = self.list_active_composition_tracks(working_composition_id)
        by_id = {track.track_id: track for track in tracks}
        if set(by_id) != set(ordered_track_ids) or len(by_id) != len(ordered_track_ids):
            raise ValueError("TRACK_ORDER_SET_MISMATCH")
        offset = max((track.track_order for track in tracks), default=-1) + len(tracks) + 1
        for track in tracks:
            track.track_order += offset
        self.session.flush()
        for order, track_id in enumerate(ordered_track_ids):
            by_id[track_id].track_order = order
        self.session.flush()

    def tombstone_composition_track(self, track: CompositionTrack) -> None:
        track.deleted_at = utc_now()
        self.session.flush()

    def restore_composition_track(
        self, track: CompositionTrack, *, target_track_order: int
    ) -> None:
        """Restore one Track while atomically rebuilding the active order."""

        tracks = self.list_active_composition_tracks(track.working_composition_id)
        if track.deleted_at is None:
            raise ValueError("TRACK_ALREADY_ACTIVE")
        if not 0 <= target_track_order <= len(tracks):
            raise ValueError("TRACK_RESTORE_ORDER_INVALID")

        offset = max((item.track_order for item in tracks), default=-1) + len(tracks) + 2
        for item in tracks:
            item.track_order += offset
        self.session.flush()

        ordered = list(tracks)
        ordered.insert(target_track_order, track)
        track.track_order = target_track_order
        track.deleted_at = None
        self.session.flush()
        for order, item in enumerate(ordered):
            item.track_order = order
        self.session.flush()

    def add_composition_clip(self, clip: CompositionClip) -> CompositionClip:
        if clip.timeline_duration is None:
            clip.timeline_duration = clip.source_out - clip.source_in
            clip.loop_enabled = False
            clip.loop_phase = 0
        clip_end = clip.timeline_start + clip.timeline_duration
        if self.active_clip_overlap_exists(
            working_composition_id=clip.working_composition_id,
            track_id=clip.track_id,
            timeline_start=clip.timeline_start,
            timeline_end=clip_end,
        ):
            raise ValueError("같은 Track의 active Clip은 겹칠 수 없습니다.")
        self.session.add(clip)
        self.session.flush()
        return clip

    def get_composition_clip(
        self,
        working_composition_id: UUID,
        clip_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> CompositionClip | None:
        statement = select(CompositionClip).where(
            CompositionClip.working_composition_id == working_composition_id,
            CompositionClip.clip_id == clip_id,
        )
        if not include_deleted:
            statement = statement.where(CompositionClip.deleted_at.is_(None))
        return self.session.scalar(statement)

    def active_clip_overlap_exists(
        self,
        *,
        working_composition_id: UUID,
        track_id: UUID,
        timeline_start: int,
        timeline_end: int,
        exclude_clip_id: UUID | None = None,
    ) -> bool:
        """반개구간 기준으로 같은 Track의 active Clip 중첩을 확인한다."""

        if timeline_start < 0 or timeline_end <= timeline_start:
            raise ValueError("검사할 Timeline 구간이 유효하지 않습니다.")
        existing_end = CompositionClip.timeline_start + CompositionClip.timeline_duration
        statement = select(CompositionClip.clip_id).where(
            CompositionClip.working_composition_id == working_composition_id,
            CompositionClip.track_id == track_id,
            CompositionClip.deleted_at.is_(None),
            CompositionClip.timeline_start < timeline_end,
            existing_end > timeline_start,
        )
        if exclude_clip_id is not None:
            statement = statement.where(CompositionClip.clip_id != exclude_clip_id)
        return self.session.scalar(statement.limit(1)) is not None

    def list_active_composition_clips(self, track_id: UUID) -> list[CompositionClip]:
        statement = (
            select(CompositionClip)
            .where(
                CompositionClip.track_id == track_id,
                CompositionClip.deleted_at.is_(None),
            )
            .order_by(CompositionClip.timeline_start, CompositionClip.clip_id)
        )
        return list(self.session.scalars(statement))

    def list_working_composition_clips(
        self,
        working_composition_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> list[CompositionClip]:
        statement = (
            select(CompositionClip)
            .join(
                CompositionTrack,
                and_(
                    CompositionTrack.working_composition_id
                    == CompositionClip.working_composition_id,
                    CompositionTrack.track_id == CompositionClip.track_id,
                ),
            )
            .where(
                CompositionClip.working_composition_id == working_composition_id,
                CompositionTrack.deleted_at.is_(None),
            )
        )
        if not include_deleted:
            statement = statement.where(CompositionClip.deleted_at.is_(None))
        statement = statement.order_by(
            CompositionTrack.track_order,
            CompositionClip.timeline_start,
            CompositionClip.clip_id,
        )
        return list(self.session.scalars(statement))

    def tombstone_composition_clip(self, clip: CompositionClip) -> None:
        clip.deleted_at = utc_now()
        self.session.flush()

    def restore_composition_clip(self, clip: CompositionClip) -> None:
        if clip.deleted_at is None:
            raise ValueError("CLIP_ALREADY_ACTIVE")
        clip.deleted_at = None
        self.session.flush()

    def count_active_composition_clips(
        self, *, working_composition_id: UUID, track_id: UUID
    ) -> int:
        """Track 삭제 guard가 같은 WorkingComposition의 active Clip만 계산한다."""

        statement = select(func.count(CompositionClip.clip_id)).where(
            CompositionClip.working_composition_id == working_composition_id,
            CompositionClip.track_id == track_id,
            CompositionClip.deleted_at.is_(None),
        )
        return int(self.session.scalar(statement) or 0)

    def add_snapshot_track(
        self, snapshot_track: CompositionSnapshotTrack
    ) -> CompositionSnapshotTrack:
        self.session.add(snapshot_track)
        self.session.flush()
        return snapshot_track

    def list_snapshot_tracks(self, snapshot_id: UUID) -> list[CompositionSnapshotTrack]:
        statement = (
            select(CompositionSnapshotTrack)
            .where(CompositionSnapshotTrack.composition_snapshot_id == snapshot_id)
            .order_by(
                CompositionSnapshotTrack.track_order,
                CompositionSnapshotTrack.snapshot_track_id,
            )
        )
        return list(self.session.scalars(statement))

    def add_snapshot_clip(self, snapshot_clip: CompositionSnapshotClip) -> CompositionSnapshotClip:
        self.session.add(snapshot_clip)
        self.session.flush()
        return snapshot_clip

    def list_snapshot_clips(self, snapshot_track_id: UUID) -> list[CompositionSnapshotClip]:
        statement = (
            select(CompositionSnapshotClip)
            .where(CompositionSnapshotClip.snapshot_track_id == snapshot_track_id)
            .order_by(
                CompositionSnapshotClip.timeline_start,
                CompositionSnapshotClip.snapshot_clip_id,
            )
        )
        return list(self.session.scalars(statement))

    def list_snapshot_clips_for_snapshot(self, snapshot_id: UUID) -> list[CompositionSnapshotClip]:
        statement = (
            select(CompositionSnapshotClip)
            .join(
                CompositionSnapshotTrack,
                and_(
                    CompositionSnapshotTrack.composition_snapshot_id
                    == CompositionSnapshotClip.composition_snapshot_id,
                    CompositionSnapshotTrack.snapshot_track_id
                    == CompositionSnapshotClip.snapshot_track_id,
                ),
            )
            .where(CompositionSnapshotClip.composition_snapshot_id == snapshot_id)
            .order_by(
                CompositionSnapshotTrack.track_order,
                CompositionSnapshotClip.timeline_start,
                CompositionSnapshotClip.snapshot_clip_id,
            )
        )
        return list(self.session.scalars(statement))

    def add_snapshot(self, snapshot: CompositionSnapshot) -> CompositionSnapshot:
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def get_snapshot(self, snapshot_id: UUID) -> CompositionSnapshot | None:
        return self.session.get(CompositionSnapshot, snapshot_id)

    def get_project_snapshot(
        self, project_id: UUID, snapshot_id: UUID
    ) -> CompositionSnapshot | None:
        statement = select(CompositionSnapshot).where(
            CompositionSnapshot.project_id == project_id,
            CompositionSnapshot.composition_snapshot_id == snapshot_id,
        )
        return self.session.scalar(statement)

    def project_has_snapshots(self, project_id: UUID) -> bool:
        statement = select(CompositionSnapshot.composition_snapshot_id).where(
            CompositionSnapshot.project_id == project_id
        )
        return self.session.scalar(statement.limit(1)) is not None

    def get_project_selection(self, project_id: UUID) -> ProjectCompositionSelection | None:
        return self.session.get(ProjectCompositionSelection, project_id)

    def set_project_selection(
        self, project_id: UUID, snapshot_id: UUID
    ) -> ProjectCompositionSelection:
        selection = self.get_project_selection(project_id)
        if selection is None:
            selection = ProjectCompositionSelection(
                project_id=project_id,
                selected_composition_snapshot_id=snapshot_id,
            )
            self.session.add(selection)
        else:
            selection.selected_composition_snapshot_id = snapshot_id
        self.session.flush()
        return selection

    def clear_project_selection(self, project_id: UUID) -> None:
        selection = self.get_project_selection(project_id)
        if selection is not None:
            self.session.delete(selection)
            self.session.flush()

    def list_transition_states(self, workspace_id: UUID) -> list[ProjectCompositionTransitionState]:
        """Workspace의 D1 전환 상태를 N+1 없이 한 번에 조회한다."""

        selected_snapshot = CompositionSnapshot.__table__.alias("selected_snapshot")
        statement = (
            select(
                MusicProject.project_id,
                exists(
                    select(CompositionSnapshot.composition_snapshot_id).where(
                        CompositionSnapshot.project_id == MusicProject.project_id
                    )
                ),
                ProjectCompositionSelection.selected_composition_snapshot_id,
                selected_snapshot.c.project_id,
            )
            .outerjoin(
                ProjectCompositionSelection,
                ProjectCompositionSelection.project_id == MusicProject.project_id,
            )
            .outerjoin(
                selected_snapshot,
                selected_snapshot.c.composition_snapshot_id
                == ProjectCompositionSelection.selected_composition_snapshot_id,
            )
            .where(
                MusicProject.workspace_id == workspace_id,
                MusicProject.deleted_at.is_(None),
            )
        )
        return [
            ProjectCompositionTransitionState(
                project_id=row[0],
                has_snapshots=bool(row[1]),
                selected_snapshot_id=row[2],
                selected_snapshot_project_id=row[3],
            )
            for row in self.session.execute(statement)
        ]

    def get_next_snapshot_version(self, project_id: UUID) -> int:
        """Project 내부의 다음 단조 증가 Snapshot version을 반환한다."""

        latest = self.session.scalar(
            select(func.max(CompositionSnapshot.snapshot_version)).where(
                CompositionSnapshot.project_id == project_id
            )
        )
        return (latest or 0) + 1

    def list_project_snapshots(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[CompositionSnapshot]:
        statement = (
            select(CompositionSnapshot)
            .where(CompositionSnapshot.project_id == project_id)
            .order_by(
                CompositionSnapshot.snapshot_version.desc(),
                CompositionSnapshot.composition_snapshot_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_project_snapshots_after(
        self,
        project_id: UUID,
        *,
        last_snapshot_version: int | None = None,
        last_id: UUID | None = None,
        limit: int = 100,
    ) -> list[CompositionSnapshot]:
        """Project Snapshot을 version DESC keyset으로 조회한다."""

        _validate_snapshot_position(last_snapshot_version, last_id)
        statement = select(CompositionSnapshot).where(CompositionSnapshot.project_id == project_id)
        if last_snapshot_version is not None and last_id is not None:
            statement = statement.where(
                or_(
                    CompositionSnapshot.snapshot_version < last_snapshot_version,
                    and_(
                        CompositionSnapshot.snapshot_version == last_snapshot_version,
                        CompositionSnapshot.composition_snapshot_id < last_id,
                    ),
                )
            )
        statement = statement.order_by(
            CompositionSnapshot.snapshot_version.desc(),
            CompositionSnapshot.composition_snapshot_id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def list_asset_snapshots(
        self, asset_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[CompositionSnapshot]:
        statement = (
            select(CompositionSnapshot)
            .join(SnapshotItem)
            .join(AssetVersion)
            .where(AssetVersion.asset_id == asset_id)
            .distinct()
            .order_by(
                CompositionSnapshot.created_at.desc(),
                CompositionSnapshot.composition_snapshot_id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def add_snapshot_item(self, item: SnapshotItem) -> SnapshotItem:
        self.session.add(item)
        self.session.flush()
        return item

    def list_snapshot_items(
        self, snapshot_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[SnapshotItem]:
        statement = (
            select(SnapshotItem)
            .where(SnapshotItem.composition_snapshot_id == snapshot_id)
            .order_by(
                SnapshotItem.item_role,
                SnapshotItem.sort_order,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_asset_versions_with_assets(
        self, asset_version_ids: Sequence[UUID]
    ) -> list[tuple[AssetVersion, Asset]]:
        if not asset_version_ids:
            return []
        statement = (
            select(AssetVersion, Asset)
            .join(Asset, Asset.asset_id == AssetVersion.asset_id)
            .where(AssetVersion.asset_version_id.in_(asset_version_ids))
        )
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    def list_artifacts_for_versions(
        self,
        asset_version_ids: Sequence[UUID],
        *,
        limit: int,
    ) -> list[Artifact]:
        if not asset_version_ids:
            return []
        statement = (
            select(Artifact)
            .where(Artifact.asset_version_id.in_(asset_version_ids))
            .order_by(
                Artifact.asset_version_id,
                Artifact.created_at,
                Artifact.artifact_id,
            )
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def snapshot_item_exists(
        self,
        snapshot_id: UUID,
        asset_version_id: UUID,
        item_role: str,
    ) -> bool:
        statement = select(SnapshotItem.snapshot_item_id).where(
            SnapshotItem.composition_snapshot_id == snapshot_id,
            SnapshotItem.asset_version_id == asset_version_id,
            SnapshotItem.item_role == item_role,
        )
        return self.session.scalar(statement.limit(1)) is not None

    def add_processing_chain(self, chain: ProcessingChain) -> ProcessingChain:
        self.session.add(chain)
        self.session.flush()
        return chain

    def get_processing_chain(self, chain_id: UUID) -> ProcessingChain | None:
        return self.session.get(ProcessingChain, chain_id)

    def list_processing_chains(self, *, limit: int = 100, offset: int = 0) -> list[ProcessingChain]:
        statement = (
            select(ProcessingChain)
            .order_by(ProcessingChain.created_at.desc(), ProcessingChain.processing_chain_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def add_processing_step(self, step: ProcessingStep) -> ProcessingStep:
        self.session.add(step)
        self.session.flush()
        return step

    def list_processing_steps(
        self, chain_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[ProcessingStep]:
        statement = (
            select(ProcessingStep)
            .where(ProcessingStep.processing_chain_id == chain_id)
            .order_by(ProcessingStep.step_order, ProcessingStep.processing_step_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def processing_step_order_exists(self, chain_id: UUID, step_order: int) -> bool:
        statement = select(ProcessingStep.processing_step_id).where(
            ProcessingStep.processing_chain_id == chain_id,
            ProcessingStep.step_order == step_order,
        )
        return self.session.scalar(statement.limit(1)) is not None


def _validate_snapshot_position(last_snapshot_version: int | None, last_id: UUID | None) -> None:
    if (last_snapshot_version is None) != (last_id is None):
        raise ValueError("Snapshot keyset 위치는 version과 ID가 함께 필요합니다.")
    if last_snapshot_version is not None and (
        type(last_snapshot_version) is not int or last_snapshot_version < 1
    ):
        raise ValueError("Snapshot version 위치가 유효하지 않습니다.")


def _validate_mix_settings(value: object) -> None:
    """후속 Service 전에도 persistence primitive의 JSON 크기를 제한한다."""

    if not isinstance(value, dict):
        raise TypeError("mix_settings는 JSON object여야 합니다.")
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(serialized.encode("utf-8")) > 8_192:
        raise ValueError("mix_settings는 UTF-8 8192 bytes 이하여야 합니다.")
