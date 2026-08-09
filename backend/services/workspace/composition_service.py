"""불변 Composition Snapshot과 Processing application use case."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.cursor_pagination import (
    COMPOSITION_SNAPSHOT_CURSOR_SORT,
    CursorCodec,
    filter_fingerprint,
)
from backend.core.exceptions import (
    ApplicationValidationError,
    CursorConfigurationError,
    IdempotencyConflictError,
    IdempotencyInProgressError,
    InvalidLimitError,
    ResourceConflictError,
    ResourceNotFoundError,
    WorkspaceBootstrapRequiredError,
)
from backend.models.workspace import (
    CompositionSnapshot,
    MusicProject,
    ProcessingChain,
    ProcessingStep,
    SnapshotItem,
)
from backend.repositories.idempotency_repository import IdempotencyRepository
from backend.repositories.workspace import (
    AssetRepository,
    CompositionRepository,
    WorkspaceRepository,
)

SNAPSHOT_ITEM_ROLES = frozenset({"lyrics", "music", "vocal", "stem", "mix"})
MAX_SNAPSHOT_ITEMS = 64
MAX_LINEAGE_ENTRIES = 16
MAX_JSON_DEPTH = 4
MAX_JSON_ENTRIES = 64
MAX_JSON_KEY_LENGTH = 64
MAX_JSON_STRING_LENGTH = 1_024
MAX_IDEMPOTENCY_KEY_LENGTH = 128
SNAPSHOT_CREATION_ATTEMPTS = 3
SNAPSHOT_IDEMPOTENCY_TTL_HOURS = 24


@dataclass(frozen=True, slots=True)
class SnapshotItemInput:
    asset_version_id: UUID
    item_role: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class CompositionSnapshotAggregate:
    snapshot: CompositionSnapshot
    items: tuple[SnapshotItem, ...]


@dataclass(frozen=True, slots=True)
class CompositionSnapshotCreation:
    aggregate: CompositionSnapshotAggregate
    replayed: bool
    response_status: int


@dataclass(frozen=True, slots=True)
class CompositionSnapshotCursorPage:
    items: tuple[CompositionSnapshot, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


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

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        cursor_codec: CursorCodec | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.cursor_codec = cursor_codec

    def create_snapshot(
        self,
        *,
        project_id: UUID,
        effective_owner_id: UUID,
        items: Sequence[SnapshotItemInput],
        mix_settings_snapshot: dict[str, Any],
        provider_versions: dict[str, Any],
        model_manifest_ids: dict[str, Any],
        idempotency_key: str,
        processing_chain_id: UUID | None = None,
    ) -> CompositionSnapshotCreation:
        _validate_uuid(project_id, "project_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        normalized_key = _normalize_idempotency_key(idempotency_key)
        if not items:
            raise ApplicationValidationError("Snapshot Item이 하나 이상 필요합니다.")
        normalized_items = self._normalize_snapshot_items(items)
        normalized_mix = _validate_json_object(
            mix_settings_snapshot, "mix_settings_snapshot"
        )
        normalized_providers = _validate_string_mapping(
            provider_versions, "provider_versions"
        )
        normalized_manifests = _validate_string_mapping(
            model_manifest_ids, "model_manifest_ids"
        )
        fingerprint = _snapshot_fingerprint(
            project_id=project_id,
            effective_owner_id=effective_owner_id,
            items=normalized_items,
            processing_chain_id=processing_chain_id,
            mix_settings_snapshot=normalized_mix,
            provider_versions=normalized_providers,
            model_manifest_ids=normalized_manifests,
        )
        scope = f"workspace:composition_snapshot:{effective_owner_id}:{project_id}"
        for attempt in range(SNAPSHOT_CREATION_ATTEMPTS):
            try:
                return self._create_snapshot_attempt(
                    project_id=project_id,
                    effective_owner_id=effective_owner_id,
                    items=normalized_items,
                    processing_chain_id=processing_chain_id,
                    mix_settings_snapshot=normalized_mix,
                    provider_versions=normalized_providers,
                    model_manifest_ids=normalized_manifests,
                    idempotency_key=normalized_key,
                    idempotency_scope=scope,
                    fingerprint=fingerprint,
                )
            except IntegrityError:
                if attempt + 1 == SNAPSHOT_CREATION_ATTEMPTS:
                    raise ResourceConflictError("CompositionSnapshot") from None
        raise AssertionError("도달할 수 없는 Snapshot 생성 상태")

    def get_snapshot(
        self, snapshot_id: UUID, *, effective_owner_id: UUID
    ) -> CompositionSnapshotAggregate:
        _validate_uuid(snapshot_id, "composition_snapshot_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        with self.session_factory() as session:
            repository = CompositionRepository(session)
            snapshot = repository.get_snapshot(snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError("CompositionSnapshot")
            self._require_project_scope(
                session, snapshot.project_id, effective_owner_id
            )
            return self._load_aggregate(repository, snapshot)

    def list_project_snapshots(
        self,
        project_id: UUID,
        *,
        effective_owner_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CompositionSnapshot]:
        with self.session_factory() as session:
            self._require_project_scope(session, project_id, effective_owner_id)
            return CompositionRepository(session).list_project_snapshots(
                project_id, limit=limit, offset=offset
            )

    def list_snapshot_page(
        self,
        project_id: UUID,
        *,
        effective_owner_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CompositionSnapshotCursorPage:
        _validate_uuid(project_id, "project_id")
        _validate_uuid(effective_owner_id, "effective_owner_id")
        _validate_page_limit(limit)
        codec = self._require_cursor_codec()
        filter_hash = filter_fingerprint(
            {
                "effective_owner_id": str(effective_owner_id),
                "include_deleted_project": False,
                "project_id": str(project_id),
                "sort": COMPOSITION_SNAPSHOT_CURSOR_SORT,
            }
        )
        position = (
            codec.decode_composition_snapshot(
                cursor,
                expected_filter_hash=filter_hash,
                expected_limit=limit,
            )
            if cursor is not None
            else None
        )
        with self.session_factory() as session:
            self._require_project_scope(session, project_id, effective_owner_id)
            rows = CompositionRepository(session).list_project_snapshots_after(
                project_id,
                last_snapshot_version=(
                    position.last_snapshot_version if position else None
                ),
                last_id=(position.last_id if position else None),
                limit=limit + 1,
            )
        has_more = len(rows) > limit
        visible = rows[:limit]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = codec.encode_composition_snapshot(
                last_snapshot_version=last.snapshot_version,
                last_id=last.composition_snapshot_id,
                filter_hash=filter_hash,
                limit=limit,
            )
        return CompositionSnapshotCursorPage(
            items=tuple(visible),
            next_cursor=next_cursor,
            has_more=has_more,
            limit=limit,
        )

    def _create_snapshot_attempt(
        self,
        *,
        project_id: UUID,
        effective_owner_id: UUID,
        items: Sequence[SnapshotItemInput],
        processing_chain_id: UUID | None,
        mix_settings_snapshot: dict[str, Any],
        provider_versions: dict[str, str],
        model_manifest_ids: dict[str, str],
        idempotency_key: str,
        idempotency_scope: str,
        fingerprint: str,
    ) -> CompositionSnapshotCreation:
        with self.session_factory() as session, session.begin():
            project = self._require_project_scope(
                session, project_id, effective_owner_id
            )
            idempotency_repository = IdempotencyRepository(session)
            try:
                claim = idempotency_repository.claim(
                    scope=idempotency_scope,
                    key=idempotency_key,
                    fingerprint=fingerprint,
                    now=datetime.now(UTC),
                    ttl_hours=SNAPSHOT_IDEMPOTENCY_TTL_HOURS,
                )
            except ValueError as error:
                if str(error) == "IDEMPOTENCY_CONFLICT":
                    raise IdempotencyConflictError() from None
                raise IdempotencyInProgressError() from None

            composition_repository = CompositionRepository(session)
            if claim.replayed:
                if claim.record.resource_type != "composition_snapshot":
                    raise IdempotencyConflictError()
                try:
                    snapshot_id = UUID(str(claim.record.resource_id))
                except (TypeError, ValueError):
                    raise IdempotencyConflictError() from None
                snapshot = composition_repository.get_snapshot(snapshot_id)
                if snapshot is None or snapshot.project_id != project_id:
                    raise IdempotencyConflictError()
                return CompositionSnapshotCreation(
                    aggregate=self._load_aggregate(composition_repository, snapshot),
                    replayed=True,
                    response_status=claim.record.response_status or 201,
                )

            if processing_chain_id is not None:
                chain = composition_repository.get_processing_chain(processing_chain_id)
                if chain is None or chain.created_by != effective_owner_id:
                    raise ResourceNotFoundError("ProcessingChain")

            asset_repository = AssetRepository(session)
            workspace_repository = WorkspaceRepository(session)
            versions = []
            for item in items:
                version = asset_repository.get_asset_version(item.asset_version_id)
                if version is None:
                    raise ResourceNotFoundError("AssetVersion")
                asset = asset_repository.get_asset(version.asset_id)
                if (
                    asset is None
                    or asset.owner_id != effective_owner_id
                    or asset.lifecycle_status != "active"
                    or asset.workspace_id not in {None, project.workspace_id}
                ):
                    raise ResourceNotFoundError("AssetVersion")
                if not workspace_repository.project_asset_exists(
                    project_id, asset.asset_id
                ):
                    raise ResourceNotFoundError("ProjectAsset")
                if (
                    version.provider_id is not None
                    and version.provider_id not in provider_versions
                ):
                    raise ApplicationValidationError(
                        "Provider가 있는 AssetVersion은 provider_versions에 포함해야 합니다."
                    )
                if (
                    version.model_manifest_id is not None
                    and version.model_manifest_id not in model_manifest_ids.values()
                ):
                    raise ApplicationValidationError(
                        "Model Manifest가 있는 AssetVersion은 model_manifest_ids에 포함해야 합니다."
                    )
                versions.append(version)

            snapshot = composition_repository.add_snapshot(
                CompositionSnapshot(
                    project_id=project_id,
                    snapshot_version=(
                        composition_repository.get_next_snapshot_version(project_id)
                    ),
                    processing_chain_id=processing_chain_id,
                    mix_settings_snapshot=dict(mix_settings_snapshot),
                    provider_versions=dict(provider_versions),
                    model_manifest_ids=dict(model_manifest_ids),
                    created_by=effective_owner_id,
                )
            )
            snapshot_items = []
            for item, version in zip(items, versions, strict=True):
                snapshot_items.append(
                    composition_repository.add_snapshot_item(
                        SnapshotItem(
                            composition_snapshot_id=(snapshot.composition_snapshot_id),
                            asset_version_id=version.asset_version_id,
                            item_role=item.item_role,
                            sort_order=item.sort_order,
                        )
                    )
                )
            idempotency_repository.complete(
                claim.record,
                resource_type="composition_snapshot",
                resource_id=str(snapshot.composition_snapshot_id),
                response_status=201,
            )
            return CompositionSnapshotCreation(
                aggregate=CompositionSnapshotAggregate(
                    snapshot=snapshot,
                    items=tuple(
                        sorted(
                            snapshot_items,
                            key=lambda item: (
                                item.item_role,
                                item.sort_order,
                                item.snapshot_item_id,
                            ),
                        )
                    ),
                ),
                replayed=False,
                response_status=201,
            )

    @staticmethod
    def _load_aggregate(
        repository: CompositionRepository,
        snapshot: CompositionSnapshot,
    ) -> CompositionSnapshotAggregate:
        return CompositionSnapshotAggregate(
            snapshot=snapshot,
            items=tuple(
                repository.list_snapshot_items(
                    snapshot.composition_snapshot_id,
                    limit=MAX_SNAPSHOT_ITEMS,
                )
            ),
        )

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
        workspace = repository.get_workspace_for_owner(
            project.workspace_id, effective_owner_id
        )
        if workspace is None or workspace.lifecycle_status != "active":
            raise ResourceNotFoundError("MusicProject")
        return project

    def _require_cursor_codec(self) -> CursorCodec:
        if self.cursor_codec is None:
            raise CursorConfigurationError()
        return self.cursor_codec

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
        if len(items) > MAX_SNAPSHOT_ITEMS:
            raise ApplicationValidationError(
                f"Snapshot Item은 최대 {MAX_SNAPSHOT_ITEMS}개까지 허용합니다."
            )
        for item in items:
            _validate_uuid(item.asset_version_id, "asset_version_id")
            role = _required_text(item.item_role, "Snapshot Item 역할")
            if role not in SNAPSHOT_ITEM_ROLES:
                raise ApplicationValidationError(
                    "Snapshot Item 역할이 공개 vocabulary에 포함되지 않습니다."
                )
            if type(item.sort_order) is not int or item.sort_order < 0:
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


def _validate_uuid(value: object, field_name: str) -> None:
    if type(value) is not UUID:
        raise ApplicationValidationError(f"{field_name} 형식이 유효하지 않습니다.")


def _validate_page_limit(limit: object) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise InvalidLimitError()


def _normalize_idempotency_key(value: object) -> str:
    if not isinstance(value, str):
        raise ApplicationValidationError("Idempotency-Key가 필요합니다.")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ApplicationValidationError("Idempotency-Key가 필요합니다.")
    return normalized


def _validate_string_mapping(value: object, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > MAX_LINEAGE_ENTRIES:
        raise ApplicationValidationError(
            f"{field_name}은 최대 {MAX_LINEAGE_ENTRIES}개의 문자열 mapping이어야 합니다."
        )
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or len(key) > MAX_JSON_KEY_LENGTH
            or not isinstance(item, str)
            or not item.strip()
            or len(item) > MAX_JSON_STRING_LENGTH
        ):
            raise ApplicationValidationError(
                f"{field_name}의 key와 value는 길이가 제한된 문자열이어야 합니다."
            )
        normalized[key.strip()] = item.strip()
    if len(normalized) != len(value):
        raise ApplicationValidationError(f"{field_name}의 key가 중복됩니다.")
    return normalized


def _validate_json_object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApplicationValidationError(f"{field_name}은 JSON object여야 합니다.")
    entries = [0]
    normalized = _normalize_json_value(value, field_name, depth=0, entries=entries)
    if not isinstance(normalized, dict):
        raise ApplicationValidationError(f"{field_name}은 JSON object여야 합니다.")
    return normalized


def _normalize_json_value(
    value: object,
    field_name: str,
    *,
    depth: int,
    entries: list[int],
) -> Any:
    if depth > MAX_JSON_DEPTH:
        raise ApplicationValidationError(
            f"{field_name}의 JSON 깊이는 {MAX_JSON_DEPTH} 이하여야 합니다."
        )
    entries[0] += 1
    if entries[0] > MAX_JSON_ENTRIES:
        raise ApplicationValidationError(
            f"{field_name}은 최대 {MAX_JSON_ENTRIES}개 항목을 허용합니다."
        )
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ApplicationValidationError(
                f"{field_name}에는 유한한 숫자만 허용합니다."
            )
        return value
    if isinstance(value, str):
        if len(value) > MAX_JSON_STRING_LENGTH:
            raise ApplicationValidationError(
                f"{field_name}의 문자열이 허용 길이를 초과합니다."
            )
        return value
    if isinstance(value, list):
        return [
            _normalize_json_value(
                item,
                field_name,
                depth=depth + 1,
                entries=entries,
            )
            for item in value
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > MAX_JSON_KEY_LENGTH:
                raise ApplicationValidationError(
                    f"{field_name}의 key 형식이 유효하지 않습니다."
                )
            normalized[key] = _normalize_json_value(
                item,
                field_name,
                depth=depth + 1,
                entries=entries,
            )
        return normalized
    raise ApplicationValidationError(f"{field_name}에는 JSON 호환 값만 허용합니다.")


def _snapshot_fingerprint(
    *,
    project_id: UUID,
    effective_owner_id: UUID,
    items: Sequence[SnapshotItemInput],
    processing_chain_id: UUID | None,
    mix_settings_snapshot: dict[str, Any],
    provider_versions: dict[str, str],
    model_manifest_ids: dict[str, str],
) -> str:
    payload = {
        "effective_owner_id": str(effective_owner_id),
        "items": sorted(
            (
                {
                    "asset_version_id": str(item.asset_version_id),
                    "item_role": item.item_role,
                    "sort_order": item.sort_order,
                }
                for item in items
            ),
            key=lambda item: (
                item["item_role"],
                item["sort_order"],
                item["asset_version_id"],
            ),
        ),
        "mix_settings_snapshot": mix_settings_snapshot,
        "model_manifest_ids": model_manifest_ids,
        "processing_chain_id": (
            str(processing_chain_id) if processing_chain_id is not None else None
        ),
        "project_id": str(project_id),
        "provider_versions": provider_versions,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
