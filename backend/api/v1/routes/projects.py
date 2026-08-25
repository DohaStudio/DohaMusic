"""MusicProject Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from backend.api.v1.dependencies import (
    get_composition_service,
    get_effective_owner_id,
    get_request_id,
    get_workspace_service,
)
from backend.api.v1.routes.common import (
    map_composition_snapshot_error,
    map_project_error,
    map_workspace_error,
    reject_owner_input,
    relative_next_url,
    relative_request_url,
    require_bootstrapped_workspace,
)
from backend.models.workspace import Artifact
from backend.schemas.workspace import (
    ArtifactDetail,
    AssetVersionDetail,
    CollectionLinks,
    CollectionResponse,
    CompositionReadItemDetail,
    CompositionReadLineage,
    CompositionReadSelection,
    CompositionReadSnapshot,
    CompositionSectionProjection,
    CompositionSelectionDetail,
    CompositionSelectionUpdateRequest,
    CompositionTrackProjection,
    CompositionWorkspaceRead,
    Pagination,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdateRequest,
    SuccessResponse,
)
from backend.services.workspace import (
    CompositionService,
    CompositionWorkspaceAggregate,
    WorkspaceService,
)

router = APIRouter(
    prefix="/projects",
    tags=["MusicProject"],
    dependencies=[Depends(reject_owner_input)],
)
WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]
CompositionServiceDependency = Annotated[CompositionService, Depends(get_composition_service)]
EffectiveOwnerDependency = Annotated[UUID, Depends(get_effective_owner_id)]


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
    "/{project_id}/composition",
    response_model=SuccessResponse[CompositionWorkspaceRead],
    operation_id="get_project_composition",
    summary="Project Composition aggregate 조회",
)
def get_project_composition(
    project_id: UUID,
    request: Request,
    service: CompositionServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
    composition_snapshot_id: UUID | None = None,
) -> SuccessResponse[CompositionWorkspaceRead]:
    try:
        aggregate = service.get_project_composition(
            project_id,
            effective_owner_id=effective_owner_id,
            composition_snapshot_id=composition_snapshot_id,
        )
    except Exception as exc:
        raise map_composition_snapshot_error(exc) from exc
    return SuccessResponse[CompositionWorkspaceRead](
        data=_composition_workspace_read(aggregate),
        request_id=get_request_id(request),
    )


@router.patch(
    "/{project_id}/composition-selection",
    response_model=SuccessResponse[CompositionSelectionDetail],
    operation_id="update_project_composition_selection",
    summary="Project current CompositionSnapshot 선택",
)
def update_project_composition_selection(
    project_id: UUID,
    payload: CompositionSelectionUpdateRequest,
    request: Request,
    service: CompositionServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
) -> SuccessResponse[CompositionSelectionDetail]:
    try:
        result = service.set_project_selection(
            project_id,
            selected_snapshot_id=payload.selected_snapshot_id,
            effective_owner_id=effective_owner_id,
        )
    except Exception as exc:
        raise map_composition_snapshot_error(exc) from exc
    return SuccessResponse[CompositionSelectionDetail](
        data=CompositionSelectionDetail.model_validate(result),
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


def _composition_workspace_read(
    aggregate: CompositionWorkspaceAggregate,
) -> CompositionWorkspaceRead:
    snapshot = aggregate.snapshot
    resolved_snapshot_id = snapshot.composition_snapshot_id if snapshot is not None else None
    items = [
        CompositionReadItemDetail(
            snapshot_item_id=resolved.item.snapshot_item_id,
            item_role=resolved.item.item_role,
            sort_order=resolved.item.sort_order,
            asset_version=AssetVersionDetail.model_validate(resolved.asset_version),
            artifacts=[_artifact_reference(artifact) for artifact in resolved.artifacts],
        )
        for resolved in aggregate.items
    ]
    track_projections = [
        CompositionTrackProjection(
            projection_id=resolved.item.snapshot_item_id,
            snapshot_item_id=resolved.item.snapshot_item_id,
            item_role=resolved.item.item_role,
            sort_order=resolved.item.sort_order,
            asset_id=resolved.asset.asset_id,
            asset_version_id=resolved.asset_version.asset_version_id,
        )
        for resolved in aggregate.items
        if resolved.item.item_role in {"music", "vocal", "stem", "mix"}
    ]
    return CompositionWorkspaceRead(
        state=aggregate.state,
        project=ProjectSummary.model_validate(aggregate.project),
        selection=CompositionReadSelection(
            selected_snapshot_id=aggregate.selected_snapshot_id,
            resolved_snapshot_id=resolved_snapshot_id,
            resolution=aggregate.resolution,
            is_current=(
                resolved_snapshot_id is not None
                and resolved_snapshot_id == aggregate.selected_snapshot_id
            ),
        ),
        snapshot=(
            CompositionReadSnapshot.model_validate(snapshot) if snapshot is not None else None
        ),
        items=items,
        track_projections=track_projections,
        section_projection=CompositionSectionProjection(),
        mix_settings_snapshot=(
            dict(snapshot.mix_settings_snapshot) if snapshot is not None else {}
        ),
        lineage=CompositionReadLineage(
            processing_chain_id=(snapshot.processing_chain_id if snapshot is not None else None),
            provider_versions=(dict(snapshot.provider_versions) if snapshot is not None else {}),
            model_manifest_ids=(dict(snapshot.model_manifest_ids) if snapshot is not None else {}),
        ),
    )


def _artifact_reference(artifact: Artifact) -> ArtifactDetail:
    artifact_id = artifact.artifact_id
    base_url = f"/api/v1/artifacts/{artifact_id}"
    content_allowed = artifact.retention_status == "active"
    return ArtifactDetail(
        artifact_id=artifact_id,
        asset_version_id=artifact.asset_version_id,
        artifact_kind=artifact.artifact_kind,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        checksum_algorithm=artifact.checksum_algorithm,
        artifact_checksum=artifact.artifact_checksum,
        producer_type=artifact.producer_type,
        producer_id=artifact.producer_id,
        run_id=artifact.run_id,
        retention_status=artifact.retention_status,
        created_at=artifact.created_at,
        content_url=f"{base_url}/content" if content_allowed else None,
        download_url=f"{base_url}/download" if content_allowed else None,
    )
