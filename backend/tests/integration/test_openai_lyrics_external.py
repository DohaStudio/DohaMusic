from __future__ import annotations

import os

import pytest

from backend.core.config import Settings
from backend.lyrics.factory import create_lyrics_generator
from backend.lyrics.interfaces import LyricsGenerationRequest

pytestmark = [pytest.mark.integration, pytest.mark.external, pytest.mark.paid]


def test_openai_lyrics_paid_smoke() -> None:
    if os.getenv("DOHAMUSIC_RUN_PAID_LYRICS_TESTS") != "1":
        pytest.skip("유료 외부 Lyrics 테스트가 명시적으로 허용되지 않았습니다.")
    api_key = os.getenv("DOHAMUSIC_LYRICS_API_KEY", "")
    if not api_key:
        pytest.skip("DOHAMUSIC_LYRICS_API_KEY가 없습니다.")
    generator = create_lyrics_generator(
        Settings(lyrics_provider="openai", lyrics_api_key=api_key)
    )
    result = generator.generate(
        LyricsGenerationRequest(
            topic="a short summer memory",
            genre="pop",
            mood="bright",
            language="en",
            keywords=("summer",),
            structure=("verse", "chorus"),
            target_duration_seconds=60,
            additional_instructions="Keep each section to two concise lines.",
        )
    )
    assert result.provider == "openai"
    assert result.sections
