"""Workspace REST API v1 Resource Route namespace."""

from backend.api.v1.routes.projects import router as projects_router
from backend.api.v1.routes.workspaces import router as workspaces_router

__all__ = ["projects_router", "workspaces_router"]
