"""Application-level exceptions independent of FastAPI."""


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ResourceNotFoundError(AppError):
    def __init__(self, resource_name: str) -> None:
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_name}을(를) 찾을 수 없습니다.",
            status_code=404,
        )


class InvalidVoiceReferenceError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="INVALID_VOICE_REFERENCE_PATH",
            message="허용된 음성 참조 파일을 확인할 수 없습니다.",
            status_code=422,
        )
