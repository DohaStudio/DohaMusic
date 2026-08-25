"""Consistent public error responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.v1.dependencies import get_request_id, is_v1_request
from backend.api.v1.responses import error_response
from backend.core.exceptions import AppError
from backend.core.logging import get_logger

logger = get_logger(__name__)


def error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if not is_v1_request(request):
            return await http_exception_handler(request, exc)
        error_code, message = _v1_http_error(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                error_code=error_code,
                message=message,
                details=[],
                request_id=get_request_id(request),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if is_v1_request(request):
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response(
                    error_code=exc.code,
                    message=exc.message,
                    details=[],
                    request_id=get_request_id(request),
                ),
                headers=exc.headers,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if is_v1_request(request):
            return JSONResponse(
                status_code=422,
                content=error_response(
                    error_code="INVALID_INPUT",
                    message="요청 입력값이 유효하지 않습니다.",
                    details=_v1_validation_details(exc.errors()),
                    request_id=get_request_id(request),
                ),
            )
        code, message = _kpop_validation_error(exc.errors())
        return JSONResponse(
            status_code=422,
            content=error_payload(code, message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        if is_v1_request(request):
            return JSONResponse(
                status_code=500,
                content=error_response(
                    error_code="INTERNAL_ERROR",
                    message="내부 오류가 발생했습니다.",
                    details=[],
                    request_id=get_request_id(request),
                ),
            )
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_ERROR", "내부 오류가 발생했습니다."),
        )


def _kpop_validation_error(errors: list[dict[str, object]]) -> tuple[str, str]:
    for error in errors:
        location = tuple(str(item) for item in error.get("loc", ()))
        error_type = str(error.get("type", ""))
        if error_type == "preset_genre_mismatch":
            return "PRESET_GENRE_MISMATCH", "K-POP 스타일과 장르가 일치하지 않습니다."
        if "generation_options" not in location:
            continue
        if "preset_id" in location:
            return "INVALID_KPOP_PRESET", "지원하지 않는 K-POP 스타일입니다."
        if "requested_bpm" in location:
            return (
                "INVALID_REQUESTED_BPM",
                "목표 BPM은 70에서 180 사이의 정수여야 합니다.",
            )
        if "language_ratio" in location:
            return (
                "INVALID_LANGUAGE_RATIO",
                "한국어와 영어 비율의 합은 100이어야 합니다.",
            )
        if "hook" in location:
            return "INVALID_HOOK_OPTIONS", "후렴 Hook 설정을 확인해 주세요."
        if "vocal_energy" in location:
            return "INVALID_VOCAL_ENERGY", "보컬 에너지 설정을 확인해 주세요."
        if "concept" in location:
            return "INVALID_CONCEPT", "곡 콘셉트는 40자 이내로 입력해 주세요."
        return "INVALID_GENERATION_OPTIONS", "K-POP 고급 설정을 확인해 주세요."
    return "INVALID_INPUT", "요청 입력값이 유효하지 않습니다."


def _v1_validation_details(
    errors: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Pydantic 내부 입력값 없이 안전한 v1 validation detail을 만든다."""

    details: list[dict[str, object]] = []
    for error in errors:
        location = [item for item in error.get("loc", ()) if isinstance(item, (str, int))]
        details.append(
            {
                "location": location,
                "error_code": str(error.get("type", "invalid_input")).upper(),
                "message": "입력값이 유효하지 않습니다.",
            }
        )
    return details


def _v1_http_error(status_code: int) -> tuple[str, str]:
    if status_code == 404:
        return "RESOURCE_NOT_FOUND", "요청한 API Resource를 찾을 수 없습니다."
    if status_code == 405:
        return "METHOD_NOT_ALLOWED", "허용되지 않은 HTTP Method입니다."
    return "HTTP_ERROR", "HTTP 요청을 처리할 수 없습니다."
