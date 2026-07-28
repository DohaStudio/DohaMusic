"""Generation job endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import get_generation_service
from backend.schemas.generated_file import GeneratedFileRead
from backend.schemas.generation import GenerationCreate, GenerationJobRead
from backend.services.generation_service import GenerationService

router = APIRouter(prefix="/generations", tags=["generations"])
GenerationServiceDependency = Annotated[
    GenerationService,
    Depends(get_generation_service),
]


@router.post(
    "",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_generation(
    request: GenerationCreate,
    service: GenerationServiceDependency,
) -> GenerationJobRead:
    return GenerationJobRead.model_validate(service.create(request))


@router.get("/{job_id}", response_model=GenerationJobRead)
def get_generation(
    job_id: str,
    service: GenerationServiceDependency,
) -> GenerationJobRead:
    return GenerationJobRead.model_validate(service.get(job_id))


@router.get("/{job_id}/files", response_model=list[GeneratedFileRead])
def list_generation_files(
    job_id: str,
    service: GenerationServiceDependency,
) -> list[GeneratedFileRead]:
    return [
        GeneratedFileRead.model_validate(item) for item in service.list_files(job_id)
    ]
