"""Consent-gated voice profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from backend.api.dependencies import get_voice_profile_service
from backend.schemas.voice_profile import VoiceProfileCreate, VoiceProfileRead
from backend.services.voice_profile_service import VoiceProfileService

router = APIRouter(prefix="/voice-profiles", tags=["voice-profiles"])
VoiceProfileServiceDependency = Annotated[
    VoiceProfileService,
    Depends(get_voice_profile_service),
]


@router.post("", response_model=VoiceProfileRead, status_code=status.HTTP_201_CREATED)
def create_voice_profile(
    request: VoiceProfileCreate,
    service: VoiceProfileServiceDependency,
) -> VoiceProfileRead:
    return VoiceProfileRead.model_validate(service.create(request))


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile(
    profile_id: str,
    service: VoiceProfileServiceDependency,
) -> Response:
    service.delete(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
