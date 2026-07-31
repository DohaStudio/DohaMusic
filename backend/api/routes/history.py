"""History and project endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from backend.api.dependencies import get_history_service
from backend.schemas.history import (
    HistoryDetailRead,
    HistoryItemRead,
    ProjectCreate,
    ProjectDetailRead,
    ProjectRead,
    ProjectUpdate,
)
from backend.services.history_service import HistoryService

router = APIRouter(tags=["history", "projects"])
ServiceDependency = Annotated[HistoryService, Depends(get_history_service)]


@router.get("/history", response_model=list[HistoryItemRead])
def list_history(
    service: ServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=200),
) -> list[HistoryItemRead]:
    return service.list_history(limit, offset, status_filter, q)


@router.get("/history/{job_id}", response_model=HistoryDetailRead)
def get_history(job_id: str, service: ServiceDependency) -> HistoryDetailRead:
    return service.get_history(job_id)


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(service: ServiceDependency) -> list[ProjectRead]:
    return service.list_projects()


@router.post(
    "/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED
)
def create_project(request: ProjectCreate, service: ServiceDependency) -> ProjectRead:
    return service.create_project(request)


@router.get("/projects/{project_id}", response_model=ProjectDetailRead)
def get_project(project_id: str, service: ServiceDependency) -> ProjectDetailRead:
    return service.get_project(project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str, request: ProjectUpdate, service: ServiceDependency
) -> ProjectRead:
    return service.update_project(project_id, request)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, service: ServiceDependency) -> Response:
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
