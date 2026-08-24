"""불변 CompositionSnapshot Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from backend.api.v1.dependencies import (
    get_composition_service,
    get_effective_owner_id,
    get_request_id,
)
from backend.api.v1.routes.common import (
    map_composition_snapshot_error,
    reject_owner_input,
    relative_next_url,
    relative_request_url,
)
from backend.schemas.workspace import (
    CollectionLinks,
    CollectionResponse,
    CompositionSnapshotCreateRequest,
    CompositionSnapshotDetail,
    CompositionSnapshotSummary,
    Pagination,
    SnapshotItemDetail,
    SuccessResponse,
)
from backend.services.workspace import (
    CompositionService,
    CompositionSnapshotAggregate,
    SnapshotItemInput,
)

router = APIRouter(
    prefix="/snapshots",
    tags=["CompositionSnapshot"],
    dependencies=[Depends(reject_owner_input)],
)
CompositionServiceDependency = Annotated[CompositionService, Depends(get_composition_service)]
EffectiveOwnerDependency = Annotated[UUID, Depends(get_effective_owner_id)]
IdempotencyKeyHeader = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description="Snapshot 생성 요청을 구분하는 opaque idempotency key",
    ),
]


@router.get(
    "",
    response_model=CollectionResponse[CompositionSnapshotSummary],
    operation_id="list_composition_snapshots",
    summary="Project별 CompositionSnapshot 목록 조회",
)
def list_composition_snapshots(
    project_id: UUID,
    request: Request,
    service: CompositionServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query()] = 20,
) -> CollectionResponse[CompositionSnapshotSummary]:
    try:
        page = service.list_snapshot_page(
            project_id,
            effective_owner_id=effective_owner_id,
            cursor=cursor,
            limit=limit,
        )
    except Exception as exc:
        raise map_composition_snapshot_error(exc) from exc
    return CollectionResponse[CompositionSnapshotSummary](
        data=[CompositionSnapshotSummary.model_validate(item) for item in page.items],
        pagination=Pagination(
            limit=page.limit,
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        ),
        links=CollectionLinks(
            self=relative_request_url(request),
            next=relative_next_url(request, page.next_cursor),
        ),
        request_id=get_request_id(request),
    )


@router.post(
    "",
    response_model=SuccessResponse[CompositionSnapshotDetail],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_composition_snapshot",
    summary="불변 CompositionSnapshot 생성",
)
def create_composition_snapshot(
    payload: CompositionSnapshotCreateRequest,
    request: Request,
    response: Response,
    service: CompositionServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
    idempotency_key: IdempotencyKeyHeader,
) -> SuccessResponse[CompositionSnapshotDetail]:
    try:
        result = service.create_snapshot(
            project_id=payload.project_id,
            effective_owner_id=effective_owner_id,
            items=[
                SnapshotItemInput(
                    asset_version_id=item.asset_version_id,
                    item_role=item.item_role,
                    sort_order=item.sort_order,
                )
                for item in payload.items
            ],
            processing_chain_id=payload.processing_chain_id,
            mix_settings_snapshot=payload.mix_settings_snapshot,
            provider_versions=payload.provider_versions,
            model_manifest_ids=payload.model_manifest_ids,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise map_composition_snapshot_error(exc) from exc
    response.status_code = result.response_status
    return SuccessResponse[CompositionSnapshotDetail](
        data=_aggregate_detail(result.aggregate),
        request_id=get_request_id(request),
    )


@router.get(
    "/{composition_snapshot_id}",
    response_model=SuccessResponse[CompositionSnapshotDetail],
    operation_id="get_composition_snapshot",
    summary="CompositionSnapshot 불변 aggregate 상세 조회",
)
def get_composition_snapshot(
    composition_snapshot_id: UUID,
    request: Request,
    service: CompositionServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
) -> SuccessResponse[CompositionSnapshotDetail]:
    try:
        aggregate = service.get_snapshot(
            composition_snapshot_id,
            effective_owner_id=effective_owner_id,
        )
    except Exception as exc:
        raise map_composition_snapshot_error(exc) from exc
    return SuccessResponse[CompositionSnapshotDetail](
        data=_aggregate_detail(aggregate),
        request_id=get_request_id(request),
    )


def _aggregate_detail(
    aggregate: CompositionSnapshotAggregate,
) -> CompositionSnapshotDetail:
    snapshot = aggregate.snapshot
    return CompositionSnapshotDetail(
        composition_snapshot_id=snapshot.composition_snapshot_id,
        project_id=snapshot.project_id,
        snapshot_version=snapshot.snapshot_version,
        processing_chain_id=snapshot.processing_chain_id,
        mix_settings_snapshot=dict(snapshot.mix_settings_snapshot),
        provider_versions=dict(snapshot.provider_versions),
        model_manifest_ids=dict(snapshot.model_manifest_ids),
        created_at=snapshot.created_at,
        items=[SnapshotItemDetail.model_validate(item) for item in aggregate.items],
    )
