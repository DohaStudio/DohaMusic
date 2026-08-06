"""Experimental OpenAI Responses API lyrics adapter."""

from __future__ import annotations

import time

from backend.lyrics.errors import (
    LyricsAuthenticationError,
    LyricsContentBlockedError,
    LyricsCostLimitExceededError,
    LyricsOutputInvalidError,
    LyricsProviderUnavailableError,
    LyricsRateLimitedError,
    LyricsRequestRejectedError,
    LyricsTimeoutError,
)
from backend.lyrics.interfaces import (
    LyricsGenerationRequest,
    LyricsGenerationResult,
    LyricsRevisionRequest,
)
from backend.lyrics.providers.openai.client import (
    OpenAIResponsesClient,
    OpenAITransport,
)
from backend.lyrics.providers.openai.config import OpenAILyricsConfig
from backend.lyrics.providers.openai.exceptions import OpenAIProviderError
from backend.lyrics.providers.openai.mapper import map_response
from backend.lyrics.providers.openai.prompts import (
    generation_prompt,
    request_payload,
    revision_prompt,
)
from backend.lyrics.providers.template import TemplateLyricsGenerator


class OpenAILyricsGenerator:
    provider = "openai"

    def __init__(
        self,
        config: OpenAILyricsConfig,
        transport: OpenAITransport | None = None,
        fallback: TemplateLyricsGenerator | None = None,
    ) -> None:
        self.config = config
        self.model_name = config.model
        self.model_version = config.model
        self.transport = transport or OpenAIResponsesClient(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self.fallback = fallback or TemplateLyricsGenerator()

    def generate(self, request: LyricsGenerationRequest) -> LyricsGenerationResult:
        try:
            return self._call(
                generation_prompt(request),
                expected_language=request.language,
                expected_structure=request.structure,
            )
        except (
            LyricsProviderUnavailableError,
            LyricsRateLimitedError,
            LyricsTimeoutError,
        ) as exc:
            if not request.allow_template_fallback:
                raise
            fallback_result = self.fallback.generate(request)
            return LyricsGenerationResult(
                title=fallback_result.title,
                sections=fallback_result.sections,
                full_text=fallback_result.full_text,
                provider=fallback_result.provider,
                model_name=fallback_result.model_name,
                model_version=fallback_result.model_version,
                generation_time_seconds=fallback_result.generation_time_seconds,
                metadata={
                    **fallback_result.metadata,
                    "fallback_used": True,
                    "fallback_from": "openai",
                    "fallback_reason": exc.code,
                    "provider_status": "local_fallback",
                },
            )

    def revise(self, request: LyricsRevisionRequest) -> LyricsGenerationResult:
        expected_structure = (
            tuple(section.section_type for section in request.source_sections)
            if request.preserve_structure
            else None
        )
        return self._call(
            revision_prompt(request),
            expected_language=request.source_language,
            expected_structure=expected_structure,
        )

    def _call(
        self,
        user_prompt: str,
        *,
        expected_language: str,
        expected_structure: tuple[str, ...] | None,
    ) -> LyricsGenerationResult:
        started_at = time.perf_counter()
        payload = request_payload(
            model=self.config.model,
            user_prompt=user_prompt,
            max_output_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
        )
        attempts = 0
        while True:
            remaining = self.config.total_deadline_seconds - (
                time.perf_counter() - started_at
            )
            if remaining <= 0:
                raise LyricsTimeoutError()
            try:
                response = self.transport.create_response(
                    payload,
                    min(self.config.timeout_seconds, remaining),
                )
                result = map_response(
                    response,
                    expected_language=expected_language,
                    expected_structure=expected_structure,
                    generation_time_seconds=time.perf_counter() - started_at,
                    input_cost_per_million=self.config.input_cost_per_million,
                    output_cost_per_million=self.config.output_cost_per_million,
                    pricing_version=self.config.pricing_version,
                )
                self._enforce_cost_limit(result)
                return self._with_request_count(result, attempts + 1)
            except OpenAIProviderError as exc:
                if exc.retryable and attempts < self.config.max_retries:
                    attempts += 1
                    continue
                raise self._public_error(exc) from exc

    def _enforce_cost_limit(self, result: LyricsGenerationResult) -> None:
        estimated = result.metadata.get("estimated_cost")
        limit = self.config.max_cost_per_request
        if (
            limit is not None
            and isinstance(estimated, (int, float))
            and estimated > limit
        ):
            raise LyricsCostLimitExceededError()

    @staticmethod
    def _with_request_count(
        result: LyricsGenerationResult, request_count: int
    ) -> LyricsGenerationResult:
        return LyricsGenerationResult(
            title=result.title,
            sections=result.sections,
            full_text=result.full_text,
            provider=result.provider,
            model_name=result.model_name,
            model_version=result.model_version,
            generation_time_seconds=result.generation_time_seconds,
            metadata={**result.metadata, "request_count": request_count},
        )

    @staticmethod
    def _public_error(error: OpenAIProviderError):
        mapping = {
            "timeout": LyricsTimeoutError,
            "unavailable": LyricsProviderUnavailableError,
            "rate_limited": LyricsRateLimitedError,
            "authentication": LyricsAuthenticationError,
            "request_rejected": LyricsRequestRejectedError,
            "content_blocked": LyricsContentBlockedError,
            "invalid_output": LyricsOutputInvalidError,
        }
        return mapping.get(error.kind, LyricsProviderUnavailableError)()
