"""Pipeline orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse

from backend.api.dependencies import get_pipeline_service
from backend.schemas.pipeline import PipelineCreate, PipelineFileRead, PipelineJobRead
from backend.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipelines", tags=["pipelines"])
ServiceDependency = Annotated[PipelineService, Depends(get_pipeline_service)]


@router.post("", response_model=PipelineJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_pipeline(
    request: PipelineCreate, service: ServiceDependency
) -> PipelineJobRead:
    return PipelineJobRead.model_validate(service.create(request))


@router.get("/{job_id}", response_model=PipelineJobRead)
def get_pipeline(job_id: str, service: ServiceDependency) -> PipelineJobRead:
    return PipelineJobRead.model_validate(service.get(job_id))


@router.get("/{job_id}/files", response_model=list[PipelineFileRead])
def list_pipeline_files(
    job_id: str, service: ServiceDependency
) -> list[PipelineFileRead]:
    return [
        PipelineFileRead.model_validate(item) for item in service.list_files(job_id)
    ]


@router.api_route(
    "/{job_id}/files/{file_id}/content",
    methods=["GET", "HEAD"],
    response_class=FileResponse,
)
def get_pipeline_file_content(
    job_id: str,
    file_id: str,
    request: Request,
    service: ServiceDependency,
) -> FileResponse:
    access = service.access_audio_file(
        job_id,
        file_id,
        download=False,
        range_header=request.headers.get("range"),
    )
    return FileResponse(
        access.path,
        media_type=access.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.api_route(
    "/{job_id}/files/{file_id}/download",
    methods=["GET", "HEAD"],
    response_class=FileResponse,
)
def download_pipeline_file(
    job_id: str,
    file_id: str,
    request: Request,
    service: ServiceDependency,
) -> FileResponse:
    access = service.access_audio_file(
        job_id,
        file_id,
        download=True,
        range_header=request.headers.get("range"),
    )
    return FileResponse(
        access.path,
        media_type=access.mime_type,
        filename=access.filename,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
