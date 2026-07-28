"""FastAPI dependency adapters for application services."""

from fastapi import Request

from backend.services.generation_service import GenerationService
from backend.services.voice_profile_service import VoiceProfileService


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def get_voice_profile_service(request: Request) -> VoiceProfileService:
    return request.app.state.voice_profile_service
