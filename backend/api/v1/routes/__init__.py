"""Workspace REST API v1 Resource Route namespace."""

from backend.api.v1.routes.assets import router as assets_router
from backend.api.v1.routes.project_assets import router as project_assets_router
from backend.api.v1.routes.projects import router as projects_router
from backend.api.v1.routes.workspaces import router as workspaces_router

__all__ = [
    "assets_router",
    "project_assets_router",
    "projects_router",
    "workspaces_router",
]
