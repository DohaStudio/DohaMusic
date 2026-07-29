"""Structured errors shared by the pipeline executor and worker."""

from __future__ import annotations


class PipelineError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        step: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.step = step
        self.retryable = retryable


class StepError(PipelineError):
    pass


class ProviderError(StepError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__("PIPELINE_PROVIDER_FAILED", message, step=step, retryable=True)


class StepTimeoutError(StepError):
    def __init__(self, step: str, timeout_seconds: float) -> None:
        super().__init__(
            "PIPELINE_STEP_TIMEOUT",
            f"{step} 단계가 {timeout_seconds}초 제한을 초과했습니다.",
            step=step,
            retryable=True,
        )


class ValidationError(StepError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__("PIPELINE_VALIDATION_FAILED", message, step=step)


class OutputError(StepError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__("PIPELINE_OUTPUT_INVALID", message, step=step)
