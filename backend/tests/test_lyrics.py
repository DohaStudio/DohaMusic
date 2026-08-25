from __future__ import annotations

import pytest

from backend.core.config import Settings
from backend.lyrics.errors import LyricsValidationError
from backend.lyrics.factory import create_lyrics_generator
from backend.lyrics.interfaces import LyricsGenerationRequest
from backend.lyrics.providers.mock import MockLyricsGenerator
from backend.lyrics.providers.template import TemplateLyricsGenerator
from backend.lyrics.validator import validate_lyrics


def request(language: str = "ko") -> LyricsGenerationRequest:
    return LyricsGenerationRequest(
        topic="끝난 사랑을 기억하는 밤" if language == "ko" else "a remembered night",
        genre="ballad",
        mood="warm",
        language=language,
        keywords=("밤", "기억") if language == "ko" else ("night", "memory"),
        structure=("verse", "pre_chorus", "chorus", "bridge", "final_chorus"),
        target_duration_seconds=180,
        additional_instructions=None,
    )


def test_mock_provider_returns_fixed_structured_result() -> None:
    result = MockLyricsGenerator().generate(request())
    assert result.provider == "mock"
    assert [section.section_type for section in result.sections] == list(request().structure)
    assert result.metadata["external_api"] is False


@pytest.mark.parametrize("language", ["ko", "en"])
def test_template_provider_generates_valid_local_draft(language: str) -> None:
    result = TemplateLyricsGenerator().generate(request(language))
    validation = validate_lyrics(result.full_text, language)
    assert validation.valid is True
    assert validation.section_count == len(request(language).structure)
    assert result.metadata["quality_status"] == "template_draft"


def test_provider_factory_defaults_to_template_and_keeps_mock() -> None:
    assert isinstance(create_lyrics_generator(Settings()), TemplateLyricsGenerator)
    assert isinstance(
        create_lyrics_generator(Settings(lyrics_provider="mock")), MockLyricsGenerator
    )


def test_provider_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="LYRICS_PROVIDER_NOT_SUPPORTED"):
        create_lyrics_generator(Settings(lyrics_provider="unknown"))


def test_validator_normalizes_sections_html_and_control_characters() -> None:
    result = validate_lyrics(
        "<script>bad()</script>[Verse 1]\n안녕\x00 <b>밤</b>\n\n[Chorus]\n기억해",
        "ko",
    )
    assert result.valid is True
    assert "script" not in result.normalized_lyrics
    assert "\x00" not in result.normalized_lyrics
    assert [section.section_type for section in result.sections] == ["verse", "chorus"]


def test_validator_distinguishes_warnings_and_errors() -> None:
    warning = validate_lyrics("같은 줄\n같은 줄\n같은 줄", "ko")
    assert warning.valid is True
    assert "후렴이 정의되지 않았습니다." in warning.warnings
    assert "동일 문장이 과도하게 반복됩니다." in warning.warnings

    invalid = validate_lyrics("[Unsupported]\n가사", "ko")
    assert invalid.valid is False
    assert invalid.errors


def test_validator_rejects_unsupported_language() -> None:
    with pytest.raises(LyricsValidationError, match="지원하지 않는 가사 언어"):
        validate_lyrics("[Verse]\n가사", "ja")
