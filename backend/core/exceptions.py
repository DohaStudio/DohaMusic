"""Application-level exceptions independent of FastAPI."""


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = headers


class ResourceNotFoundError(AppError):
    def __init__(self, resource_name: str) -> None:
        self.resource_name = resource_name
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_name}을(를) 찾을 수 없습니다.",
            status_code=404,
        )


class ResourceConflictError(AppError):
    """현재 application 상태와 충돌하는 요청."""

    def __init__(self, resource_name: str) -> None:
        self.resource_name = resource_name
        super().__init__(
            code="RESOURCE_CONFLICT",
            message=f"{resource_name} 요청이 현재 상태와 충돌합니다.",
            status_code=409,
        )


class ApplicationValidationError(AppError):
    """API transport와 독립적인 application 입력 검증 오류."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
        )


class InvalidStateError(AppError):
    """허용되지 않은 lifecycle 또는 상태 전이."""

    def __init__(self, resource_name: str) -> None:
        super().__init__(
            code="INVALID_STATE",
            message=f"{resource_name}의 현재 상태에서는 요청을 수행할 수 없습니다.",
            status_code=409,
        )


class InvalidCursorError(AppError):
    """외부에 세부 검증 원인을 노출하지 않는 cursor 오류."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            code="INVALID_CURSOR",
            message="Cursor가 유효하지 않습니다.",
            status_code=422,
        )
        self.reason = reason


class CursorConfigurationError(AppError):
    """Cursor 서명 설정이 준비되지 않은 서버 구성 오류."""

    def __init__(self) -> None:
        super().__init__(
            code="CURSOR_CONFIGURATION_ERROR",
            message="Cursor Pagination 설정을 확인할 수 없습니다.",
            status_code=500,
        )


class InvalidLimitError(AppError):
    """Cursor page 크기 범위 오류."""

    def __init__(self) -> None:
        super().__init__(
            code="INVALID_LIMIT",
            message="limit은 1에서 100 사이의 정수여야 합니다.",
            status_code=422,
        )


class InvalidVoiceReferenceError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="INVALID_VOICE_REFERENCE_PATH",
            message="허용된 음성 참조 파일을 확인할 수 없습니다.",
            status_code=422,
        )
