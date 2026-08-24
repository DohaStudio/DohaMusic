"""Voice conversion job endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import get_voice_conversion_service
from backend.schemas.voice_conversion import (
    VoiceConversionCreate,
    VoiceConversionFileRead,
    VoiceConversionJobRead,
)
from backend.services.voice_conversion_service import VoiceConversionService

router = APIRouter(prefix="/voice-conversion", tags=["voice-conversion"])
ServiceDependency = Annotated[VoiceConversionService, Depends(get_voice_conversion_service)]


@router.post("", response_model=VoiceConversionJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_voice_conversion(
    request: VoiceConversionCreate, service: ServiceDependency
) -> VoiceConversionJobRead:
    return VoiceConversionJobRead.model_validate(service.create(request))


@router.get("/{job_id}", response_model=VoiceConversionJobRead)
def get_voice_conversion(job_id: str, service: ServiceDependency) -> VoiceConversionJobRead:
    return VoiceConversionJobRead.model_validate(service.get(job_id))


@router.get("/{job_id}/files", response_model=list[VoiceConversionFileRead])
def list_voice_conversion_files(
    job_id: str, service: ServiceDependency
) -> list[VoiceConversionFileRead]:
    return [VoiceConversionFileRead.model_validate(item) for item in service.list_files(job_id)]
