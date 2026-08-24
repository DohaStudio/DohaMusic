from __future__ import annotations

import json

import pytest

from backend.core.config import Settings
from backend.lyrics.errors import (
    LyricsAuthenticationError,
    LyricsContentBlockedError,
    LyricsCostLimitExceededError,
    LyricsOutputInvalidError,
    LyricsRateLimitedError,
    LyricsTimeoutError,
)
from backend.lyrics.factory import create_lyrics_generator
from backend.lyrics.interfaces import LyricsGenerationRequest, LyricsRevisionRequest
from backend.lyrics.providers.openai.adapter import OpenAILyricsGenerator
from backend.lyrics.providers.openai.config import OpenAILyricsConfig
from backend.lyrics.providers.openai.exceptions import OpenAIProviderError
from backend.lyrics.providers.template import TemplateLyricsGenerator


def generation_request(*, fallback: bool = False) -> LyricsGenerationRequest:
    return LyricsGenerationRequest(
        topic="a remembered night",
        genre="ballad",
        mood="warm",
        language="en",
        keywords=("night", "memory"),
        structure=("verse", "chorus"),
        target_duration_seconds=120,
        additional_instructions=None,
        allow_template_fallback=fallback,
    )


def completed_response(
    *,
    sections: list[dict[str, object]] | None = None,
    language: str = "en",
    raw_text: str | None = None,
) -> dict[str, object]:
    sections = sections or [
        {"type": "verse", "label": "Verse", "lines": ["A quiet night"]},
        {"type": "chorus", "label": "Chorus", "lines": ["Memory returns"]},
    ]
    payload = {
        "title": "Night Memory",
        "language": language,
        "sections": sections,
        "full_text": "ignored in favor of validated sections",
        "warnings": [],
    }
    return {
        "status": "completed",
        "model": "gpt-5-mini-2025-08-07",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": raw_text if raw_text is not None else json.dumps(payload),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "input_tokens_details": {"cached_tokens": 10},
        },
    }


class FakeTransport:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.calls: list[tuple[dict[str, object], float]] = []

    def create_response(
        self, payload: dict[str, object], timeout_seconds: float
    ) -> dict[str, object]:
        self.calls.append((payload, timeout_seconds))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, dict)
        return result


def config(**overrides: object) -> OpenAILyricsConfig:
    values: dict[str, object] = {
        "api_key": "test-key",
        "model": "gpt-5-mini-2025-08-07",
        "base_url": "https://api.openai.com/v1",
        "timeout_seconds": 1.0,
        "total_deadline_seconds": 5.0,
        "max_retries": 1,
        "temperature": None,
        "max_output_tokens": 1000,
        "input_cost_per_million": None,
        "output_cost_per_million": None,
        "pricing_version": "",
        "max_cost_per_request": None,
    }
    values.update(overrides)
    return OpenAILyricsConfig(**values)  # type: ignore[arg-type]


def test_openai_adapter_maps_strict_response_and_request_policy() -> None:
    transport = FakeTransport(completed_response())
    result = OpenAILyricsGenerator(config(), transport=transport).generate(generation_request())
    assert result.provider == "openai"
    assert [section.section_type for section in result.sections] == [
        "verse",
        "chorus",
    ]
    assert result.metadata["estimated_cost"] is None
    request_payload = transport.calls[0][0]
    assert request_payload["store"] is False
    assert request_payload["text"]["format"]["strict"] is True  # type: ignore[index]


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (completed_response(raw_text="not-json"), LyricsOutputInvalidError),
        (completed_response(language="ko"), LyricsOutputInvalidError),
        (
            completed_response(
                sections=[
                    {"type": "chorus", "label": "Chorus", "lines": ["First"]},
                    {"type": "verse", "label": "Verse", "lines": ["Second"]},
                ]
            ),
            LyricsOutputInvalidError,
        ),
        (
            completed_response(
                sections=[
                    {"type": "verse", "label": "Verse", "lines": ["ok", 1]},
                    {"type": "chorus", "label": "Chorus", "lines": ["ok"]},
                ]
            ),
            LyricsOutputInvalidError,
        ),
    ],
)
def test_openai_adapter_rejects_invalid_outputs(
    response: dict[str, object], error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        OpenAILyricsGenerator(config(), transport=FakeTransport(response)).generate(
            generation_request()
        )


def test_openai_adapter_retries_retryable_errors() -> None:
    transport = FakeTransport(
        OpenAIProviderError("rate_limited", retryable=True), completed_response()
    )
    result = OpenAILyricsGenerator(config(), transport=transport).generate(generation_request())
    assert result.metadata["request_count"] == 2
    assert len(transport.calls) == 2


@pytest.mark.parametrize(
    ("provider_error", "public_error"),
    [
        (OpenAIProviderError("timeout", retryable=True), LyricsTimeoutError),
        (OpenAIProviderError("rate_limited", retryable=True), LyricsRateLimitedError),
        (OpenAIProviderError("authentication"), LyricsAuthenticationError),
        (OpenAIProviderError("content_blocked"), LyricsContentBlockedError),
    ],
)
def test_openai_adapter_maps_sanitized_errors(
    provider_error: Exception, public_error: type[Exception]
) -> None:
    with pytest.raises(public_error):
        OpenAILyricsGenerator(
            config(max_retries=0), transport=FakeTransport(provider_error)
        ).generate(generation_request())


def test_template_fallback_is_explicit_and_records_actual_provider() -> None:
    provider_error = OpenAIProviderError("timeout", retryable=True)
    with pytest.raises(LyricsTimeoutError):
        OpenAILyricsGenerator(
            config(max_retries=0), transport=FakeTransport(provider_error)
        ).generate(generation_request())

    result = OpenAILyricsGenerator(
        config(max_retries=0),
        transport=FakeTransport(OpenAIProviderError("timeout", retryable=True)),
    ).generate(generation_request(fallback=True))
    assert result.provider == "template"
    assert result.metadata["fallback_used"] is True
    assert result.metadata["fallback_from"] == "openai"


def test_cost_is_centralized_and_limit_is_enforced_after_response() -> None:
    adapter = OpenAILyricsGenerator(
        config(
            input_cost_per_million=0.25,
            output_cost_per_million=2.0,
            pricing_version="2026-07-29",
            max_cost_per_request=0.00001,
        ),
        transport=FakeTransport(completed_response()),
    )
    with pytest.raises(LyricsCostLimitExceededError):
        adapter.generate(generation_request())


def test_cost_metadata_uses_configured_snapshot() -> None:
    result = OpenAILyricsGenerator(
        config(
            input_cost_per_million=0.25,
            output_cost_per_million=2.0,
            pricing_version="2026-07-29",
        ),
        transport=FakeTransport(completed_response()),
    ).generate(generation_request())
    assert result.metadata["estimated_cost"] == pytest.approx(0.000125)
    assert result.metadata["currency"] == "USD"
    assert result.metadata["pricing_version"] == "2026-07-29"


def test_revision_prompt_preserves_structure_and_excludes_local_identifiers() -> None:
    source = TemplateLyricsGenerator().generate(generation_request())
    transport = FakeTransport(completed_response())
    adapter = OpenAILyricsGenerator(config(), transport=transport)
    result = adapter.revise(
        LyricsRevisionRequest(
            source_title=source.title,
            source_language="en",
            source_sections=source.sections,
            source_full_text=source.full_text,
            instruction="make the chorus more concise",
            preserve_structure=True,
        )
    )
    assert len(result.sections) == 2
    serialized = json.dumps(transport.calls[0][0])
    assert "lyrics_id" not in serialized
    assert "voice" not in serialized


def test_factory_requires_key_only_for_explicit_openai_provider() -> None:
    with pytest.raises(ValueError, match="LYRICS_API_KEY_MISSING"):
        create_lyrics_generator(Settings(lyrics_provider="openai"))
    generator = create_lyrics_generator(
        Settings(lyrics_provider="openai", lyrics_api_key="test-key")
    )
    assert isinstance(generator, OpenAILyricsGenerator)
