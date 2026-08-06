"""Workspace REST API v1 envelope 생성기."""

from __future__ import annotations

from typing import Any

from backend.schemas.workspace.common import ErrorResponse, SuccessResponse


def success_response(*, data: Any, request_id: str) -> dict[str, Any]:
    return SuccessResponse[Any](data=data, request_id=request_id).model_dump(
        mode="json"
    )


def error_response(
    *,
    error_code: str,
    message: str,
    details: list[dict[str, object]],
    request_id: str,
) -> dict[str, Any]:
    return ErrorResponse(
        error={
            "error_code": error_code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    ).model_dump(mode="json")
