"""FastAPI dependency adapters for application services."""

from fastapi import Request

from backend.services.generation_service import GenerationService
from backend.services.lyrics_service import LyricsService
from backend.services.pipeline_service import PipelineService
from backend.services.stem_service import StemService
from backend.services.voice_profile_service import VoiceProfileService
from backend.services.voice_conversion_service import VoiceConversionService


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def get_lyrics_service(request: Request) -> LyricsService:
    return request.app.state.lyrics_service


def get_pipeline_service(request: Request) -> PipelineService:
    return request.app.state.pipeline_service


def get_voice_profile_service(request: Request) -> VoiceProfileService:
    return request.app.state.voice_profile_service


def get_stem_service(request: Request) -> StemService:
    return request.app.state.stem_service


def get_voice_conversion_service(request: Request) -> VoiceConversionService:
    return request.app.state.voice_conversion_service
