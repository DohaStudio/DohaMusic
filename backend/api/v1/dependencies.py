"""Workspace REST API v1 공통 request dependency와 middleware."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response

from backend.core.exceptions import AppError
from backend.services.workspace import (
    ArtifactApplicationService,
    AssetService,
    CompositionService,
    WorkspaceService,
)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def is_v1_request(request: Request) -> bool:
    path = request.url.path
    return path == "/api/v1" or path.startswith("/api/v1/")


def normalize_request_id(value: str | None) -> str:
    """검증된 opaque ID를 유지하고 그 외 입력에는 새 UUID를 발급한다."""

    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def get_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str):
        return existing
    request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    return request_id


def get_workspace_service(request: Request) -> WorkspaceService:
    """App composition root에서 구성한 WorkspaceService를 제공한다."""

    service = getattr(request.app.state, "workspace_service", None)
    if not isinstance(service, WorkspaceService):
        raise RuntimeError("WorkspaceService가 구성되지 않았습니다.")
    return service


def get_asset_service(request: Request) -> AssetService:
    """App composition root에서 구성한 AssetService를 제공한다."""

    service = getattr(request.app.state, "asset_service", None)
    if not isinstance(service, AssetService):
        raise RuntimeError("AssetService가 구성되지 않았습니다.")
    return service


def get_artifact_application_service(request: Request) -> ArtifactApplicationService:
    """App composition root에서 구성한 ArtifactApplicationService를 제공한다."""

    service = getattr(request.app.state, "artifact_application_service", None)
    if not isinstance(service, ArtifactApplicationService):
        raise RuntimeError("ArtifactApplicationService가 구성되지 않았습니다.")
    return service


def get_composition_service(request: Request) -> CompositionService:
    """App composition root에서 구성한 CompositionService를 제공한다."""

    service = getattr(request.app.state, "composition_service", None)
    if not isinstance(service, CompositionService):
        raise RuntimeError("CompositionService가 구성되지 않았습니다.")
    return service


def get_effective_owner_id(request: Request) -> UUID:
    """단일 사용자 Workspace의 신뢰된 effective owner를 반환한다."""

    workspaces = get_workspace_service(request).list_workspaces(limit=1)
    if not workspaces:
        raise AppError(
            code="WORKSPACE_BOOTSTRAP_REQUIRED",
            message="기본 Workspace Bootstrap이 필요합니다.",
            status_code=409,
        )
    return workspaces[0].owner_id


def register_request_id_middleware(app: FastAPI) -> None:
    """모든 요청에 correlation ID를 부여하되 payload는 v1만 변경한다."""

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = get_request_id(request)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
