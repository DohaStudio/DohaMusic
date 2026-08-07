"""Workspace REST API v1 Router와 첫 Resource Route 등록."""

from fastapi import APIRouter

from backend.api.v1.routes import projects_router, workspaces_router

router = APIRouter()
router.include_router(workspaces_router)
router.include_router(projects_router)
