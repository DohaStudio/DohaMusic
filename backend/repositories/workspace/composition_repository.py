"""Composition Snapshot과 Processing aggregate persistence operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.asset import AssetVersion
from backend.models.workspace.composition import (
    CompositionSnapshot,
    ProcessingChain,
    ProcessingStep,
    SnapshotItem,
)


class CompositionRepository:
    """불변 Composition aggregate를 commit 없이 현재 transaction에 추가한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_snapshot(self, snapshot: CompositionSnapshot) -> CompositionSnapshot:
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def get_snapshot(self, snapshot_id: UUID) -> CompositionSnapshot | None:
        return self.session.get(CompositionSnapshot, snapshot_id)

    def list_project_snapshots(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[CompositionSnapshot]:
        statement = (
            select(CompositionSnapshot)
            .where(CompositionSnapshot.project_id == project_id)
            .order_by(
                CompositionSnapshot.snapshot_version.desc(),
                CompositionSnapshot.composition_snapshot_id,
            )
            .limit(limit)
            .offset(offset)
        )
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
                SnapshotItem.snapshot_item_id,
            )
            .limit(limit)
            .offset(offset)
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

    def list_processing_chains(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[ProcessingChain]:
        statement = (
            select(ProcessingChain)
            .order_by(
                ProcessingChain.created_at.desc(), ProcessingChain.processing_chain_id
            )
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
