"""Asset Resource REST API."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from backend.api.v1.dependencies import (
    get_asset_service,
    get_request_id,
    get_workspace_service,
)
from backend.api.v1.routes.common import (
    asset_not_found,
    map_asset_error,
    map_workspace_error,
    reject_owner_input,
    relative_next_url,
    relative_request_url,
    require_bootstrapped_workspace,
    workspace_not_found,
)
from backend.models.workspace import Asset, AssetType, Workspace
from backend.schemas.workspace import (
    AssetCreateRequest,
    AssetDetail,
    AssetSummary,
    AssetUpdateRequest,
    CollectionLinks,
    CollectionResponse,
    Pagination,
    SuccessResponse,
)
from backend.services.workspace import AssetService, WorkspaceService

router = APIRouter(
    prefix="/assets",
    tags=["Asset"],
    dependencies=[Depends(reject_owner_input)],
)
AssetServiceDependency = Annotated[AssetService, Depends(get_asset_service)]
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


def _effective_workspace(
    service: WorkspaceService,
    workspace_id: UUID | None = None,
) -> Workspace:
    require_bootstrapped_workspace(service)
    effective_workspace = service.list_workspaces(limit=1)[0]
    if workspace_id is None:
        return effective_workspace
    try:
        workspace = service.get_workspace(workspace_id)
    except Exception as exc:
        raise map_workspace_error(exc) from exc
    if workspace.owner_id != effective_workspace.owner_id:
        raise workspace_not_found()
    return workspace


def _owned_asset(
    service: AssetService,
    workspace_service: WorkspaceService,
    asset_id: UUID,
) -> Asset:
    workspace = _effective_workspace(workspace_service)
    try:
        asset = service.get_asset(asset_id)
    except Exception as exc:
        raise map_asset_error(exc) from exc
    if asset.owner_id != workspace.owner_id:
        raise asset_not_found()
    return asset


@router.get(
    "",
    response_model=CollectionResponse[AssetSummary],
    operation_id="list_assets",
    summary="Asset 목록 조회",
)
def list_assets(
    request: Request,
    asset_service: AssetServiceDependency,
    workspace_service: WorkspaceServiceDependency,
    workspace_id: UUID | None = None,
    asset_type: AssetType | None = None,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query()] = 50,
) -> CollectionResponse[AssetSummary]:
    workspace = _effective_workspace(workspace_service, workspace_id)
    try:
        page = asset_service.list_asset_page(
            owner_id=workspace.owner_id,
            workspace_id=workspace_id,
            asset_type=asset_type,
            cursor=cursor,
            limit=limit,
        )
    except Exception as exc:
        raise map_asset_error(exc) from exc
    return CollectionResponse[AssetSummary](
        data=[AssetSummary.model_validate(item) for item in page.items],
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
    response_model=SuccessResponse[AssetDetail],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_asset",
    summary="Asset 생성",
)
def create_asset(
    payload: AssetCreateRequest,
    request: Request,
    asset_service: AssetServiceDependency,
    workspace_service: WorkspaceServiceDependency,
) -> SuccessResponse[AssetDetail]:
    workspace = _effective_workspace(workspace_service, payload.workspace_id)
    try:
        asset = asset_service.create_asset(
            owner_id=workspace.owner_id,
            workspace_id=payload.workspace_id,
            asset_type=payload.asset_type,
            lifecycle_status=payload.lifecycle_status,
        )
    except Exception as exc:
        raise map_asset_error(exc) from exc
    return SuccessResponse[AssetDetail](
        data=AssetDetail.model_validate(asset),
        request_id=get_request_id(request),
    )


@router.get(
    "/{asset_id}",
    response_model=SuccessResponse[AssetDetail],
    operation_id="get_asset",
    summary="Asset 상세 조회",
)
def get_asset(
    asset_id: UUID,
    request: Request,
    asset_service: AssetServiceDependency,
    workspace_service: WorkspaceServiceDependency,
) -> SuccessResponse[AssetDetail]:
    asset = _owned_asset(asset_service, workspace_service, asset_id)
    return SuccessResponse[AssetDetail](
        data=AssetDetail.model_validate(asset),
        request_id=get_request_id(request),
    )


@router.patch(
    "/{asset_id}",
    response_model=SuccessResponse[AssetDetail],
    operation_id="update_asset",
    summary="Asset Metadata 수정",
)
def update_asset(
    asset_id: UUID,
    payload: AssetUpdateRequest,
    request: Request,
    asset_service: AssetServiceDependency,
    workspace_service: WorkspaceServiceDependency,
) -> SuccessResponse[AssetDetail]:
    _owned_asset(asset_service, workspace_service, asset_id)
    lifecycle_status = cast(str, payload.lifecycle_status)
    try:
        asset = asset_service.update_asset_metadata(
            asset_id,
            lifecycle_status=lifecycle_status,
        )
    except Exception as exc:
        raise map_asset_error(exc) from exc
    return SuccessResponse[AssetDetail](
        data=AssetDetail.model_validate(asset),
        request_id=get_request_id(request),
    )


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="delete_asset",
    summary="Asset Soft Delete",
)
def delete_asset(
    asset_id: UUID,
    asset_service: AssetServiceDependency,
    workspace_service: WorkspaceServiceDependency,
) -> Response:
    _owned_asset(asset_service, workspace_service, asset_id)
    try:
        asset_service.delete_asset(asset_id)
    except Exception as exc:
        raise map_asset_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
