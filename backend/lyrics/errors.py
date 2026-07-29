"""Stable lyrics error codes independent of FastAPI."""

from backend.core.exceptions import AppError


class LyricsError(AppError):
    pass


class LyricsValidationError(LyricsError):
    def __init__(self, message: str = "가사 입력값이 유효하지 않습니다.") -> None:
        super().__init__("LYRICS_VALIDATION_FAILED", message, 422)


class LyricsGenerationError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_GENERATION_FAILED", "가사 초안 생성에 실패했습니다.", 500
        )


class LyricsOutputInvalidError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_OUTPUT_INVALID", "생성된 가사 구조가 유효하지 않습니다.", 500
        )
