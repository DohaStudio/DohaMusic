"""불변 Composition Snapshot과 Processing application use case."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.models.workspace import (
    CompositionSnapshot,
    ProcessingChain,
    ProcessingStep,
    SnapshotItem,
)
from backend.repositories.workspace import (
    AssetRepository,
    CompositionRepository,
    WorkspaceRepository,
)


@dataclass(frozen=True)
class SnapshotItemInput:
    asset_version_id: UUID
    item_role: str
    sort_order: int


@dataclass(frozen=True)
class ProcessingStepInput:
    step_order: int
    step_type: str
    settings_snapshot: dict[str, Any]


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ApplicationValidationError(f"{field_name}은(는) 비어 있을 수 없습니다.")
    return normalized


class CompositionService:
    """Snapshot과 Processing 정의를 원자적으로 생성한다."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create_snapshot(
        self,
        *,
        project_id: UUID,
        snapshot_version: int,
        items: Sequence[SnapshotItemInput],
        mix_settings_snapshot: dict[str, Any],
        provider_versions: dict[str, Any],
        model_manifest_ids: dict[str, Any],
        created_by: UUID,
        processing_chain_id: UUID | None = None,
    ) -> CompositionSnapshot:
        if snapshot_version < 1:
            raise ApplicationValidationError("snapshot_version은 1 이상이어야 합니다.")
        if not items:
            raise ApplicationValidationError("Snapshot Item이 하나 이상 필요합니다.")
        normalized_items = self._normalize_snapshot_items(items)
        try:
            with self.session_factory() as session, session.begin():
                workspace_repository = WorkspaceRepository(session)
                asset_repository = AssetRepository(session)
                composition_repository = CompositionRepository(session)
                project = workspace_repository.get_project(project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                if processing_chain_id is not None:
                    if (
                        composition_repository.get_processing_chain(processing_chain_id)
                        is None
                    ):
                        raise ResourceNotFoundError("ProcessingChain")
                versions = []
                for item in normalized_items:
                    version = asset_repository.get_asset_version(item.asset_version_id)
                    if version is None:
                        raise ResourceNotFoundError("AssetVersion")
                    asset = asset_repository.get_asset(version.asset_id)
                    if asset is None:
                        raise ResourceNotFoundError("Asset")
                    if (
                        asset.workspace_id is not None
                        and asset.workspace_id != project.workspace_id
                    ):
                        raise ApplicationValidationError(
                            "Snapshot AssetVersion의 Workspace 범위가 다릅니다."
                        )
                    versions.append(version)
                snapshot = composition_repository.add_snapshot(
                    CompositionSnapshot(
                        project_id=project_id,
                        snapshot_version=snapshot_version,
                        processing_chain_id=processing_chain_id,
                        mix_settings_snapshot=dict(mix_settings_snapshot),
                        provider_versions=dict(provider_versions),
                        model_manifest_ids=dict(model_manifest_ids),
                        created_by=created_by,
                    )
                )
                for item, version in zip(normalized_items, versions, strict=True):
                    composition_repository.add_snapshot_item(
                        SnapshotItem(
                            composition_snapshot_id=(snapshot.composition_snapshot_id),
                            asset_version_id=version.asset_version_id,
                            item_role=item.item_role,
                            sort_order=item.sort_order,
                        )
                    )
            return snapshot
        except IntegrityError:
            raise ResourceConflictError("CompositionSnapshot") from None

    def get_snapshot(self, snapshot_id: UUID) -> CompositionSnapshot:
        with self.session_factory() as session:
            snapshot = CompositionRepository(session).get_snapshot(snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError("CompositionSnapshot")
            return snapshot

    def list_project_snapshots(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[CompositionSnapshot]:
        with self.session_factory() as session:
            if WorkspaceRepository(session).get_project(project_id) is None:
                raise ResourceNotFoundError("MusicProject")
            return CompositionRepository(session).list_project_snapshots(
                project_id, limit=limit, offset=offset
            )

    def create_processing_chain(
        self,
        *,
        name: str,
        chain_version: str,
        chain_checksum: str,
        created_by: UUID,
        steps: Sequence[ProcessingStepInput] = (),
    ) -> ProcessingChain:
        normalized_name = _required_text(name, "ProcessingChain 이름")
        normalized_version = _required_text(chain_version, "Chain version")
        normalized_checksum = _required_text(chain_checksum, "Chain checksum")
        normalized_steps = self._normalize_processing_steps(steps)
        try:
            with self.session_factory() as session, session.begin():
                repository = CompositionRepository(session)
                chain = repository.add_processing_chain(
                    ProcessingChain(
                        name=normalized_name,
                        chain_version=normalized_version,
                        chain_checksum=normalized_checksum,
                        created_by=created_by,
                    )
                )
                for step in normalized_steps:
                    repository.add_processing_step(
                        ProcessingStep(
                            processing_chain_id=chain.processing_chain_id,
                            step_order=step.step_order,
                            step_type=step.step_type,
                            settings_snapshot=dict(step.settings_snapshot),
                        )
                    )
            return chain
        except IntegrityError:
            raise ResourceConflictError("ProcessingChain") from None

    def add_processing_step(
        self,
        chain_id: UUID,
        *,
        step_order: int,
        step_type: str,
        settings_snapshot: dict[str, Any],
    ) -> ProcessingStep:
        normalized_step = self._normalize_processing_steps(
            [
                ProcessingStepInput(
                    step_order=step_order,
                    step_type=step_type,
                    settings_snapshot=settings_snapshot,
                )
            ]
        )[0]
        try:
            with self.session_factory() as session, session.begin():
                repository = CompositionRepository(session)
                if repository.get_processing_chain(chain_id) is None:
                    raise ResourceNotFoundError("ProcessingChain")
                if repository.processing_step_order_exists(chain_id, step_order):
                    raise ResourceConflictError("ProcessingStep 순서")
                step = repository.add_processing_step(
                    ProcessingStep(
                        processing_chain_id=chain_id,
                        step_order=normalized_step.step_order,
                        step_type=normalized_step.step_type,
                        settings_snapshot=dict(normalized_step.settings_snapshot),
                    )
                )
            return step
        except IntegrityError:
            raise ResourceConflictError("ProcessingStep") from None

    def get_processing_chain(self, chain_id: UUID) -> ProcessingChain:
        with self.session_factory() as session:
            chain = CompositionRepository(session).get_processing_chain(chain_id)
            if chain is None:
                raise ResourceNotFoundError("ProcessingChain")
            return chain

    @staticmethod
    def _normalize_snapshot_items(
        items: Sequence[SnapshotItemInput],
    ) -> list[SnapshotItemInput]:
        normalized: list[SnapshotItemInput] = []
        role_orders: set[tuple[str, int]] = set()
        version_roles: set[tuple[UUID, str]] = set()
        for item in items:
            role = _required_text(item.item_role, "Snapshot Item 역할")
            if item.sort_order < 0:
                raise ApplicationValidationError(
                    "Snapshot Item 순서는 0 이상이어야 합니다."
                )
            if (role, item.sort_order) in role_orders:
                raise ResourceConflictError("Snapshot Item 역할과 순서")
            if (item.asset_version_id, role) in version_roles:
                raise ResourceConflictError("Snapshot Item Version과 역할")
            role_orders.add((role, item.sort_order))
            version_roles.add((item.asset_version_id, role))
            normalized.append(
                SnapshotItemInput(item.asset_version_id, role, item.sort_order)
            )
        return normalized

    @staticmethod
    def _normalize_processing_steps(
        steps: Sequence[ProcessingStepInput],
    ) -> list[ProcessingStepInput]:
        normalized: list[ProcessingStepInput] = []
        orders: set[int] = set()
        for step in steps:
            if step.step_order < 1:
                raise ApplicationValidationError(
                    "ProcessingStep 순서는 1 이상이어야 합니다."
                )
            if step.step_order in orders:
                raise ResourceConflictError("ProcessingStep 순서")
            orders.add(step.step_order)
            normalized.append(
                ProcessingStepInput(
                    step.step_order,
                    _required_text(step.step_type, "ProcessingStep 유형"),
                    dict(step.settings_snapshot),
                )
            )
        return normalized
