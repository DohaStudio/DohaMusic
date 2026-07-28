"""Stem separation job endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import get_stem_service
from backend.schemas.stem import StemCreate, StemFileRead, StemJobRead
from backend.services.stem_service import StemService

router = APIRouter(prefix="/stems", tags=["stems"])
StemServiceDependency = Annotated[StemService, Depends(get_stem_service)]


@router.post("", response_model=StemJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_stem_job(
    request: StemCreate,
    service: StemServiceDependency,
) -> StemJobRead:
    return StemJobRead.model_validate(service.create(request))


@router.get("/{job_id}", response_model=StemJobRead)
def get_stem_job(job_id: str, service: StemServiceDependency) -> StemJobRead:
    return StemJobRead.model_validate(service.get(job_id))


@router.get("/{job_id}/files", response_model=list[StemFileRead])
def list_stem_files(
    job_id: str,
    service: StemServiceDependency,
) -> list[StemFileRead]:
    return [StemFileRead.model_validate(item) for item in service.list_files(job_id)]
