"""ProjectAsset Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from backend.api.v1.dependencies import get_request_id, get_workspace_service
from backend.api.v1.routes.common import (
    map_project_asset_error,
    reject_owner_input,
    relative_next_url,
    relative_request_url,
    require_bootstrapped_workspace,
)
from backend.schemas.workspace import (
    CollectionLinks,
    CollectionResponse,
    Pagination,
    ProjectAssetCreateRequest,
    ProjectAssetSummary,
    SuccessResponse,
)
from backend.services.workspace import WorkspaceService

router = APIRouter(
    prefix="/projects/{project_id}/assets",
    tags=["ProjectAsset"],
    dependencies=[Depends(reject_owner_input)],
)
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.get(
    "",
    response_model=CollectionResponse[ProjectAssetSummary],
    operation_id="list_project_assets",
    summary="ProjectAsset 연결 목록 조회",
)
def list_project_assets(
    project_id: UUID,
    request: Request,
    service: WorkspaceServiceDependency,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query()] = 50,
) -> CollectionResponse[ProjectAssetSummary]:
    require_bootstrapped_workspace(service)
    try:
        page = service.list_project_asset_page(
            project_id,
            cursor=cursor,
            limit=limit,
        )
    except Exception as exc:
        raise map_project_asset_error(exc) from exc
    return CollectionResponse[ProjectAssetSummary](
        data=[ProjectAssetSummary.model_validate(item) for item in page.items],
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
    response_model=SuccessResponse[ProjectAssetSummary],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_project_asset",
    summary="기존 Asset을 Project에 연결",
)
def create_project_asset(
    project_id: UUID,
    payload: ProjectAssetCreateRequest,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[ProjectAssetSummary]:
    require_bootstrapped_workspace(service)
    try:
        project_asset = service.attach_asset(
            project_id=project_id,
            asset_id=payload.asset_id,
            role=payload.role,
            display_order=payload.display_order,
        )
    except Exception as exc:
        raise map_project_asset_error(exc) from exc
    return SuccessResponse[ProjectAssetSummary](
        data=ProjectAssetSummary.model_validate(project_asset),
        request_id=get_request_id(request),
    )


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="delete_project_asset",
    summary="ProjectAsset 관계 Soft Delete",
)
def delete_project_asset(
    project_id: UUID,
    asset_id: UUID,
    service: WorkspaceServiceDependency,
) -> Response:
    require_bootstrapped_workspace(service)
    try:
        service.detach_asset(project_id=project_id, asset_id=asset_id)
    except Exception as exc:
        raise map_project_asset_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
