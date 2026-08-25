"""Workspace REST API v1 Resource Route namespace."""

from backend.api.v1.routes.artifacts import router as artifacts_router
from backend.api.v1.routes.assets import router as assets_router
from backend.api.v1.routes.jobs import router as jobs_router
from backend.api.v1.routes.project_assets import router as project_assets_router
from backend.api.v1.routes.projects import router as projects_router
from backend.api.v1.routes.snapshots import router as snapshots_router
from backend.api.v1.routes.working_compositions import (
    router as working_compositions_router,
)
from backend.api.v1.routes.workspaces import router as workspaces_router

__all__ = [
    "artifacts_router",
    "assets_router",
    "jobs_router",
    "project_assets_router",
    "projects_router",
    "snapshots_router",
    "working_compositions_router",
    "workspaces_router",
]
