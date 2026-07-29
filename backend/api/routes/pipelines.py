"""Pipeline orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

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
