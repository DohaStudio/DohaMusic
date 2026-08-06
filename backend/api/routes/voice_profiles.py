"""Consent-gated voice profile endpoints."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Response,
    UploadFile,
    status,
)

from backend.api.dependencies import get_voice_profile_service, get_voice_upload_service
from backend.schemas.voice_profile import VoiceProfileCreate, VoiceProfileRead
from backend.services.voice_profile_service import VoiceProfileService
from backend.services.voice_upload_service import VoiceUploadService

router = APIRouter(prefix="/voice-profiles", tags=["voice-profiles"])
VoiceProfileServiceDependency = Annotated[
    VoiceProfileService,
    Depends(get_voice_profile_service),
]
VoiceUploadServiceDependency = Annotated[
    VoiceUploadService,
    Depends(get_voice_upload_service),
]


@router.post("", response_model=VoiceProfileRead, status_code=status.HTTP_201_CREATED)
def create_voice_profile(
    request: VoiceProfileCreate,
    service: VoiceProfileServiceDependency,
) -> VoiceProfileRead:
    return VoiceProfileRead.model_validate(service.create(request))


@router.post(
    "/upload", response_model=VoiceProfileRead, status_code=status.HTTP_201_CREATED
)
async def upload_voice_profile(
    service: VoiceUploadServiceDependency,
    name: Annotated[str, Form(min_length=1, max_length=100)],
    file: Annotated[UploadFile | None, File()] = None,
    consent_confirmed: Annotated[bool | None, Form()] = None,
    consent_text_version: Annotated[str, Form(min_length=1, max_length=50)] = "v1",
    content_length: Annotated[int | None, Header()] = None,
) -> VoiceProfileRead:
    profile = await service.upload(
        file=file,
        name=name,
        consent_confirmed=consent_confirmed,
        consent_text_version=consent_text_version,
        content_length=content_length,
    )
    return VoiceProfileRead.model_validate(profile)


@router.get("", response_model=list[VoiceProfileRead])
def list_voice_profiles(
    service: VoiceProfileServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VoiceProfileRead]:
    return [
        VoiceProfileRead.model_validate(item)
        for item in service.list(limit=limit, offset=offset)
    ]


@router.get("/{profile_id}", response_model=VoiceProfileRead)
def get_voice_profile(
    profile_id: str,
    service: VoiceProfileServiceDependency,
) -> VoiceProfileRead:
    return VoiceProfileRead.model_validate(service.get(profile_id))


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile(
    profile_id: str,
    service: VoiceProfileServiceDependency,
) -> Response:
    service.delete(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
