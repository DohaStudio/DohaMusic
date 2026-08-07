"""Workspace Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from backend.api.v1.dependencies import get_request_id, get_workspace_service
from backend.api.v1.routes.common import (
    map_workspace_error,
    relative_next_url,
    relative_request_url,
    reject_owner_input,
    require_bootstrapped_workspace,
)
from backend.schemas.workspace import (
    CollectionLinks,
    CollectionResponse,
    Pagination,
    SuccessResponse,
    WorkspaceDetail,
    WorkspaceSummary,
    WorkspaceUpdateRequest,
)
from backend.services.workspace import WorkspaceService

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspace"],
    dependencies=[Depends(reject_owner_input)],
)
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.get(
    "",
    response_model=CollectionResponse[WorkspaceSummary],
    operation_id="list_workspaces",
)
def list_workspaces(
    request: Request,
    service: WorkspaceServiceDependency,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[WorkspaceSummary]:
    require_bootstrapped_workspace(service)
    page = service.list_workspace_page(cursor=cursor, limit=limit)
    return CollectionResponse[WorkspaceSummary](
        data=[WorkspaceSummary.model_validate(item) for item in page.items],
        pagination=Pagination(
            limit=page.limit, next_cursor=page.next_cursor, has_more=page.has_more
        ),
        links=CollectionLinks(
            self=relative_request_url(request),
            next=relative_next_url(request, page.next_cursor),
        ),
        request_id=get_request_id(request),
    )


@router.get(
    "/{workspace_id}",
    response_model=SuccessResponse[WorkspaceDetail],
    operation_id="get_workspace",
)
def get_workspace(
    workspace_id: UUID,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[WorkspaceDetail]:
    require_bootstrapped_workspace(service)
    try:
        workspace = service.get_workspace(workspace_id)
    except Exception as exc:
        raise map_workspace_error(exc) from exc
    return SuccessResponse[WorkspaceDetail](
        data=WorkspaceDetail.model_validate(workspace),
        request_id=get_request_id(request),
    )


@router.patch(
    "/{workspace_id}",
    response_model=SuccessResponse[WorkspaceDetail],
    operation_id="update_workspace",
)
def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[WorkspaceDetail]:
    require_bootstrapped_workspace(service)
    try:
        workspace = service.rename_workspace(workspace_id, payload.name)
    except Exception as exc:
        raise map_workspace_error(exc) from exc
    return SuccessResponse[WorkspaceDetail](
        data=WorkspaceDetail.model_validate(workspace),
        request_id=get_request_id(request),
    )
