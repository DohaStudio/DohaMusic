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


class LyricsApiKeyMissingError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_API_KEY_MISSING", "외부 가사 Provider 설정이 필요합니다.", 503
        )


class LyricsProviderUnavailableError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_PROVIDER_UNAVAILABLE",
            "외부 가사 Provider를 사용할 수 없습니다.",
            503,
        )


class LyricsRateLimitedError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_RATE_LIMITED", "외부 가사 Provider 요청 한도를 초과했습니다.", 429
        )


class LyricsTimeoutError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_TIMEOUT", "외부 가사 Provider 응답 시간이 초과되었습니다.", 504
        )


class LyricsAuthenticationError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_AUTHENTICATION_FAILED",
            "외부 가사 Provider 인증에 실패했습니다.",
            503,
        )


class LyricsRequestRejectedError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_REQUEST_REJECTED", "외부 가사 Provider가 요청을 거부했습니다.", 422
        )


class LyricsContentBlockedError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_CONTENT_BLOCKED",
            "가사 요청이 콘텐츠 정책에 따라 차단되었습니다.",
            422,
        )


class LyricsCostLimitExceededError(LyricsError):
    def __init__(self) -> None:
        super().__init__(
            "LYRICS_COST_LIMIT_EXCEEDED", "가사 요청 비용 제한을 초과했습니다.", 422
        )


class LyricsRevisionError(LyricsError):
    def __init__(self, message: str = "가사 수정에 실패했습니다.") -> None:
        super().__init__("LYRICS_REVISION_FAILED", message, 422)
