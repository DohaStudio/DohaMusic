"""Workspace Resource Router의 공통 transport helper."""

from __future__ import annotations

from fastapi import Request

from backend.core.exceptions import (
    AppError,
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.services.workspace import WorkspaceService


def require_bootstrapped_workspace(service: WorkspaceService) -> None:
    if not service.list_workspaces(limit=1):
        raise AppError(
            code="WORKSPACE_BOOTSTRAP_REQUIRED",
            message="기본 Workspace Bootstrap이 필요합니다.",
            status_code=409,
        )


def reject_owner_input(request: Request) -> None:
    """소유권 필드는 공개 Resource API 입력으로 받지 않는다."""

    if {"owner_id", "created_by"}.intersection(request.query_params):
        raise invalid_input("소유권 필드는 API 입력으로 지정할 수 없습니다.")


def workspace_not_found() -> AppError:
    return AppError(
        code="WORKSPACE_NOT_FOUND",
        message="Workspace를 찾을 수 없습니다.",
        status_code=404,
    )


def project_not_found() -> AppError:
    return AppError(
        code="PROJECT_NOT_FOUND",
        message="Project를 찾을 수 없습니다.",
        status_code=404,
    )


def workspace_name_conflict() -> AppError:
    return AppError(
        code="WORKSPACE_NAME_CONFLICT",
        message="같은 이름의 Workspace가 이미 존재합니다.",
        status_code=409,
    )


def project_title_conflict() -> AppError:
    return AppError(
        code="PROJECT_TITLE_CONFLICT",
        message="같은 제목의 Project가 이미 존재합니다.",
        status_code=409,
    )


def asset_not_found() -> AppError:
    return AppError(
        code="ASSET_NOT_FOUND",
        message="Asset을 찾을 수 없습니다.",
        status_code=404,
    )


def project_asset_not_found() -> AppError:
    return AppError(
        code="PROJECT_ASSET_NOT_FOUND",
        message="ProjectAsset 연결을 찾을 수 없습니다.",
        status_code=404,
    )


def project_asset_conflict() -> AppError:
    return AppError(
        code="PROJECT_ASSET_CONFLICT",
        message="Project와 Asset이 이미 연결돼 있습니다.",
        status_code=409,
    )


def invalid_input(message: str = "요청 입력값이 유효하지 않습니다.") -> AppError:
    return AppError(code="INVALID_INPUT", message=message, status_code=422)


def relative_request_url(request: Request) -> str:
    return request.url.path + (f"?{request.url.query}" if request.url.query else "")


def relative_next_url(request: Request, next_cursor: str | None) -> str | None:
    if next_cursor is None:
        return None
    url = request.url.include_query_params(cursor=next_cursor)
    return url.path + (f"?{url.query}" if url.query else "")


def map_workspace_error(exc: Exception) -> AppError:
    if isinstance(exc, ResourceNotFoundError):
        return workspace_not_found()
    if isinstance(exc, ResourceConflictError):
        return workspace_name_conflict()
    if isinstance(exc, ApplicationValidationError):
        return invalid_input(exc.message)
    raise exc


def map_project_error(exc: Exception) -> AppError:
    if isinstance(exc, ResourceNotFoundError):
        return project_not_found()
    if isinstance(exc, ResourceConflictError):
        return project_title_conflict()
    if isinstance(exc, ApplicationValidationError):
        return invalid_input(exc.message)
    raise exc


def map_project_asset_error(exc: Exception) -> AppError:
    if isinstance(exc, ResourceNotFoundError):
        if exc.resource_name == "MusicProject":
            return project_not_found()
        if exc.resource_name == "Asset":
            return asset_not_found()
        if exc.resource_name == "ProjectAsset":
            return project_asset_not_found()
    if isinstance(exc, ResourceConflictError) and exc.resource_name == "ProjectAsset":
        return project_asset_conflict()
    if isinstance(exc, ApplicationValidationError):
        return invalid_input(exc.message)
    raise exc
