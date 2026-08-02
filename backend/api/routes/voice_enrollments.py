"""Guided Voice Enrollment API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile, status

from backend.api.dependencies import get_voice_enrollment_service
from backend.schemas.voice_enrollment import (
    VoiceEnrollmentCreateRequest,
    VoiceEnrollmentResponse,
    VoiceEnrollmentSubmitRequest,
    VoiceSampleResponse,
)
from backend.services.voice_enrollment_service import VoiceEnrollmentService

router = APIRouter(prefix="/voice-enrollments", tags=["voice-enrollments"])
VoiceEnrollmentServiceDependency = Annotated[
    VoiceEnrollmentService,
    Depends(get_voice_enrollment_service),
]
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]
VOICE_SAMPLE_UPLOAD_RESPONSES = {
    422: {
        "description": (
            "파일 길이, decode 또는 WAV codec/bit depth가 등록 계약에 맞지 않음"
        ),
        "content": {
            "application/json": {
                "examples": {
                    "unsupported_wav_codec": {
                        "summary": "PCM16이 아닌 WAV",
                        "value": {
                            "error": {
                                "code": "VOICE_SAMPLE_UNSUPPORTED_CODEC",
                                "message": (
                                    "이 WAV 파일의 오디오 형식은 지원하지 않습니다. "
                                    "PCM 16-bit WAV로 변환해 주세요."
                                ),
                            }
                        },
                    }
                }
            }
        },
    }
}


def _private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post(
    "", response_model=VoiceEnrollmentResponse, status_code=status.HTTP_201_CREATED
)
def create_voice_enrollment(
    request: VoiceEnrollmentCreateRequest,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> VoiceEnrollmentResponse:
    _private_no_store(response)
    return service.create(request, idempotency_key)


@router.get("/{enrollment_id}", response_model=VoiceEnrollmentResponse)
def get_voice_enrollment(
    enrollment_id: str,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
) -> VoiceEnrollmentResponse:
    _private_no_store(response)
    return service.get(enrollment_id)


@router.post(
    "/{enrollment_id}/samples",
    response_model=VoiceSampleResponse,
    status_code=status.HTTP_201_CREATED,
    responses=VOICE_SAMPLE_UPLOAD_RESPONSES,
)
async def upload_voice_sample(
    enrollment_id: str,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
    source_type: Annotated[str, Form(min_length=1, max_length=32)],
    category: Annotated[
        str, Form(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    file: Annotated[UploadFile | None, File()] = None,
    prompt_id: Annotated[
        str | None, Form(max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    ] = None,
    idempotency_key: IdempotencyKey = None,
) -> VoiceSampleResponse:
    _private_no_store(response)
    return await service.upload_sample(
        enrollment_id=enrollment_id,
        file=file,
        source_type=source_type,
        prompt_id=prompt_id,
        category=category,
        idempotency_key=idempotency_key,
    )


@router.get("/{enrollment_id}/samples/{sample_id}", response_model=VoiceSampleResponse)
def get_voice_sample(
    enrollment_id: str,
    sample_id: str,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
) -> VoiceSampleResponse:
    _private_no_store(response)
    return service.get_sample(enrollment_id, sample_id)


@router.delete(
    "/{enrollment_id}/samples/{sample_id}", response_model=VoiceSampleResponse
)
def delete_voice_sample(
    enrollment_id: str,
    sample_id: str,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
) -> VoiceSampleResponse:
    _private_no_store(response)
    return service.delete_sample(enrollment_id, sample_id)


@router.post(
    "/{enrollment_id}/submit",
    response_model=VoiceEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_voice_enrollment(
    enrollment_id: str,
    request: VoiceEnrollmentSubmitRequest,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> VoiceEnrollmentResponse:
    _private_no_store(response)
    return service.submit(enrollment_id, request, idempotency_key)


@router.post("/{enrollment_id}/cancel", response_model=VoiceEnrollmentResponse)
def cancel_voice_enrollment(
    enrollment_id: str,
    service: VoiceEnrollmentServiceDependency,
    response: Response,
) -> VoiceEnrollmentResponse:
    _private_no_store(response)
    return service.cancel(enrollment_id)
