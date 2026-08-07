"""MusicProject Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from backend.api.v1.dependencies import get_request_id, get_workspace_service
from backend.api.v1.routes.common import (
    map_project_error,
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
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdateRequest,
    SuccessResponse,
)
from backend.services.workspace import WorkspaceService

router = APIRouter(
    prefix="/projects",
    tags=["MusicProject"],
    dependencies=[Depends(reject_owner_input)],
)
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.get(
    "",
    response_model=CollectionResponse[ProjectSummary],
    operation_id="list_projects",
    summary="MusicProject 목록 조회",
)
def list_projects(
    workspace_id: UUID,
    request: Request,
    service: WorkspaceServiceDependency,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query()] = 50,
) -> CollectionResponse[ProjectSummary]:
    require_bootstrapped_workspace(service)
    try:
        page = service.list_project_page(workspace_id, cursor=cursor, limit=limit)
    except Exception as exc:
        raise map_workspace_error(exc) from exc
    return CollectionResponse[ProjectSummary](
        data=[ProjectSummary.model_validate(item) for item in page.items],
        pagination=Pagination(
            limit=page.limit, next_cursor=page.next_cursor, has_more=page.has_more
        ),
        links=CollectionLinks(
            self=relative_request_url(request),
            next=relative_next_url(request, page.next_cursor),
        ),
        request_id=get_request_id(request),
    )


@router.post(
    "",
    response_model=SuccessResponse[ProjectDetail],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_project",
    summary="MusicProject 생성",
)
def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[ProjectDetail]:
    require_bootstrapped_workspace(service)
    try:
        workspace = service.get_workspace(payload.workspace_id)
    except Exception as exc:
        raise map_workspace_error(exc) from exc
    try:
        project = service.create_project(
            workspace_id=payload.workspace_id,
            title=payload.title,
            description=payload.description,
            created_by=workspace.owner_id,
        )
    except Exception as exc:
        raise map_project_error(exc) from exc
    return SuccessResponse[ProjectDetail](
        data=ProjectDetail.model_validate(project),
        request_id=get_request_id(request),
    )


@router.get(
    "/{project_id}",
    response_model=SuccessResponse[ProjectDetail],
    operation_id="get_project",
    summary="MusicProject 상세 조회",
)
def get_project(
    project_id: UUID,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[ProjectDetail]:
    require_bootstrapped_workspace(service)
    try:
        project = service.get_project(project_id)
    except Exception as exc:
        raise map_project_error(exc) from exc
    return SuccessResponse[ProjectDetail](
        data=ProjectDetail.model_validate(project),
        request_id=get_request_id(request),
    )


@router.patch(
    "/{project_id}",
    response_model=SuccessResponse[ProjectDetail],
    operation_id="update_project",
    summary="MusicProject Metadata 수정",
)
def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    request: Request,
    service: WorkspaceServiceDependency,
) -> SuccessResponse[ProjectDetail]:
    require_bootstrapped_workspace(service)
    changes: dict[str, str] = {}
    if "title" in payload.model_fields_set and payload.title is not None:
        changes["title"] = payload.title
    if "description" in payload.model_fields_set and payload.description is not None:
        changes["description"] = payload.description
    try:
        project = service.update_project_metadata(project_id, **changes)
    except Exception as exc:
        raise map_project_error(exc) from exc
    return SuccessResponse[ProjectDetail](
        data=ProjectDetail.model_validate(project),
        request_id=get_request_id(request),
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="delete_project",
    summary="MusicProject Soft Delete",
)
def delete_project(project_id: UUID, service: WorkspaceServiceDependency) -> Response:
    require_bootstrapped_workspace(service)
    try:
        service.delete_project(project_id)
    except Exception as exc:
        raise map_project_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
