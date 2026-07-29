"""Map a Responses API object into the provider-neutral lyrics contract."""

from __future__ import annotations

import json

from backend.lyrics.constants import SUPPORTED_SECTION_TYPES
from backend.lyrics.interfaces import LyricsGenerationResult, LyricsSection
from backend.lyrics.providers.openai.exceptions import OpenAIProviderError
from backend.lyrics.providers.openai.pricing import estimate_cost
from backend.lyrics.validator import normalize_section_type, render_sections


def map_response(
    response: dict[str, object],
    *,
    expected_language: str,
    expected_structure: tuple[str, ...] | None,
    generation_time_seconds: float,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
    pricing_version: str,
) -> LyricsGenerationResult:
    if response.get("status") != "completed":
        raise OpenAIProviderError("invalid_output")
    text = _output_text(response)
    data = _load_json(text)
    language = data.get("language")
    if language != expected_language:
        raise OpenAIProviderError("invalid_output")
    sections = _sections(data.get("sections"))
    structure = tuple(section.section_type for section in sections)
    if expected_structure is not None and structure != expected_structure:
        raise OpenAIProviderError("invalid_output")

    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    input_tokens = _non_negative_int(usage.get("input_tokens"))
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    input_details = (
        usage.get("input_tokens_details")
        if isinstance(usage.get("input_tokens_details"), dict)
        else {}
    )
    cached_tokens = _non_negative_int(input_details.get("cached_tokens"))
    cost = estimate_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_per_million=input_cost_per_million,
        output_cost_per_million=output_cost_per_million,
        pricing_version=pricing_version,
    )
    model = response.get("model")
    warnings = data.get("warnings")
    safe_warnings = (
        [item for item in warnings if isinstance(item, str)]
        if isinstance(warnings, list)
        else []
    )
    return LyricsGenerationResult(
        title=data.get("title") if isinstance(data.get("title"), str) else None,
        sections=sections,
        full_text=render_sections(sections),
        provider="openai",
        model_name=model if isinstance(model, str) else "openai-unknown",
        model_version=model if isinstance(model, str) else None,
        generation_time_seconds=generation_time_seconds,
        metadata={
            "provider_status": "Experimental",
            "structured_output": "json_schema_strict",
            "request_count": 1,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "estimated_cost": cost.amount,
            "currency": cost.currency,
            "pricing_version": cost.pricing_version,
            "provider_warnings": safe_warnings,
            "fallback_used": False,
        },
    )


def _output_text(response: dict[str, object]) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise OpenAIProviderError("invalid_output")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise OpenAIProviderError("content_blocked")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                return part["text"]
    raise OpenAIProviderError("invalid_output")


def _load_json(text: str) -> dict[str, object]:
    candidate = text.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise OpenAIProviderError("invalid_output") from exc
    if not isinstance(data, dict):
        raise OpenAIProviderError("invalid_output")
    return data


def _sections(value: object) -> tuple[LyricsSection, ...]:
    if not isinstance(value, list) or not value:
        raise OpenAIProviderError("invalid_output")
    sections: list[LyricsSection] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise OpenAIProviderError("invalid_output")
        section_type = normalize_section_type(item["type"])
        lines = item.get("lines")
        if section_type not in SUPPORTED_SECTION_TYPES or not isinstance(lines, list):
            raise OpenAIProviderError("invalid_output")
        if not all(isinstance(line, str) for line in lines):
            raise OpenAIProviderError("invalid_output")
        normalized_lines = tuple(line.strip() for line in lines)
        if not normalized_lines or any(not line for line in normalized_lines):
            raise OpenAIProviderError("invalid_output")
        sections.append(LyricsSection(section_type, normalized_lines))
    return tuple(sections)


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0
