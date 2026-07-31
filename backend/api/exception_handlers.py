"""Consistent public error responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.exceptions import AppError
from backend.core.logging import get_logger

logger = get_logger(__name__)


def error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        code, message = _kpop_validation_error(exc.errors())
        return JSONResponse(
            status_code=422,
            content=error_payload(code, message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
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
