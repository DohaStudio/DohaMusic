"""Lyrics generation and validation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from backend.api.dependencies import get_lyrics_service
from backend.schemas.lyrics import (
    LyricsCreate,
    LyricsDocumentRead,
    LyricsRevisionCreate,
    LyricsValidationRead,
    LyricsValidationRequest,
)
from backend.services.lyrics_service import LyricsService

router = APIRouter(prefix="/lyrics", tags=["lyrics"])
LyricsServiceDependency = Annotated[LyricsService, Depends(get_lyrics_service)]


@router.post("", response_model=LyricsDocumentRead, status_code=status.HTTP_201_CREATED)
def create_lyrics(
    request: LyricsCreate, service: LyricsServiceDependency
) -> LyricsDocumentRead:
    return LyricsDocumentRead.model_validate(service.create(request))


@router.post(
    "/{lyrics_id}/revise",
    response_model=LyricsDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def revise_lyrics(
    lyrics_id: str, request: LyricsRevisionCreate, service: LyricsServiceDependency
) -> LyricsDocumentRead:
    return LyricsDocumentRead.model_validate(service.revise(lyrics_id, request))


@router.post("/validate", response_model=LyricsValidationRead)
def validate_lyrics(
    request: LyricsValidationRequest, service: LyricsServiceDependency
) -> LyricsValidationRead:
    return LyricsValidationRead.model_validate(service.validate(request))


@router.get("/{lyrics_id}", response_model=LyricsDocumentRead)
def get_lyrics(lyrics_id: str, service: LyricsServiceDependency) -> LyricsDocumentRead:
    return LyricsDocumentRead.model_validate(service.get(lyrics_id))


@router.delete("/{lyrics_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lyrics(lyrics_id: str, service: LyricsServiceDependency) -> Response:
    service.delete(lyrics_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
