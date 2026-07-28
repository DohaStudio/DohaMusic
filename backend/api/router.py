"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes.generations import router as generations_router
from backend.api.routes.health import router as health_router
from backend.api.routes.voice_profiles import router as voice_profiles_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(generations_router, prefix="/api")
api_router.include_router(voice_profiles_router, prefix="/api")
