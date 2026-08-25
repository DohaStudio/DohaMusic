"""Workspace REST API v1 Router와 첫 Resource Route 등록."""

from fastapi import APIRouter

from backend.api.v1.routes import (
    artifacts_router,
    assets_router,
    jobs_router,
    project_assets_router,
    projects_router,
    snapshots_router,
    working_compositions_router,
    workspaces_router,
)

router = APIRouter()
router.include_router(workspaces_router)
router.include_router(projects_router)
router.include_router(project_assets_router)
router.include_router(assets_router)
router.include_router(artifacts_router)
router.include_router(snapshots_router)
router.include_router(jobs_router)
router.include_router(working_compositions_router)
