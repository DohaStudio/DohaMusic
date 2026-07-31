"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes.generations import router as generations_router
from backend.api.routes.health import router as health_router
from backend.api.routes.lyrics import router as lyrics_router
from backend.api.routes.pipelines import router as pipelines_router
from backend.api.routes.stems import router as stems_router
from backend.api.routes.voice_conversion import router as voice_conversion_router
from backend.api.routes.voice_profiles import router as voice_profiles_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(generations_router, prefix="/api")
api_router.include_router(lyrics_router, prefix="/api")
api_router.include_router(pipelines_router, prefix="/api")
api_router.include_router(stems_router, prefix="/api")
api_router.include_router(voice_profiles_router, prefix="/api")
api_router.include_router(voice_conversion_router, prefix="/api")
