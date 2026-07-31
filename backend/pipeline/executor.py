"""Sequential workflow executor with step-level retries and metrics."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from backend.core.logging import get_logger
from backend.pipeline.context import PipelineContext
from backend.pipeline.errors import PipelineError, ProviderError, StepTimeoutError
from backend.pipeline.steps import PipelineStep

StepStartedCallback = Callable[[PipelineStep], None]
logger = get_logger(__name__)


class PipelineExecutor:
    def __init__(
        self,
        steps: Sequence[PipelineStep],
        max_retries: int,
        step_timeout_seconds: float,
    ) -> None:
        self.steps = list(steps)
        self.max_retries = max_retries
        self.step_timeout_seconds = step_timeout_seconds

    def execute(
        self, context: PipelineContext, on_step_started: StepStartedCallback
    ) -> PipelineContext:
        for step in self.steps:
            on_step_started(step)
            self._execute_step(step, context)
        return context

    def _execute_step(self, step: PipelineStep, context: PipelineContext) -> None:
        max_attempts = self.max_retries + 1
        for attempt in range(1, max_attempts + 1):
            started_at = time.perf_counter()
            try:
                metrics = step.execute(context)
                elapsed = time.perf_counter() - started_at
                if elapsed > self.step_timeout_seconds:
                    raise StepTimeoutError(step.name, self.step_timeout_seconds)
                context.step_execution.append(
                    {
                        "step": step.name,
                        "attempt": attempt,
                        "status": "COMPLETED",
                        "execution_time_seconds": round(elapsed, 6),
                        **metrics,
                    }
                )
                logger.info(
                    "pipeline_step_completed job_id=%s step=%s attempt=%s duration_ms=%s",
                    context.job_id,
                    step.name,
                    attempt,
                    round(elapsed * 1_000, 2),
                )
                return
            except PipelineError as exc:
                error = exc
            except Exception as exc:
                logger.exception(
                    "pipeline_provider_exception job_id=%s step=%s attempt=%s error_type=%s",
                    context.job_id,
                    step.name,
                    attempt,
                    type(exc).__name__,
                )
                error = ProviderError(step.name, "Provider 단계 실행이 실패했습니다.")
            elapsed = time.perf_counter() - started_at
            context.step_execution.append(
                {
                    "step": step.name,
                    "attempt": attempt,
                    "status": "FAILED",
                    "execution_time_seconds": round(elapsed, 6),
                    "error_code": error.code,
                }
            )
            context.errors.append(
                {
                    "step": step.name,
                    "attempt": attempt,
                    "code": error.code,
                    "message": error.message,
                }
            )
            logger.warning(
                "pipeline_step_attempt_failed job_id=%s step=%s attempt=%s code=%s",
                context.job_id,
                step.name,
                attempt,
                error.code,
            )
            if not error.retryable or attempt >= max_attempts:
                raise error
