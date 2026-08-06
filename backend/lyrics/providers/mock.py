"""Fixed-output lyrics provider for contract tests."""

from __future__ import annotations

import time

from backend.lyrics.interfaces import (
    LyricsGenerationRequest,
    LyricsGenerationResult,
    LyricsSection,
)
from backend.lyrics.validator import render_sections


class MockLyricsGenerator:
    provider = "mock"
    model_name = "mock-lyrics-generator"
    model_version = "1"

    def generate(self, request: LyricsGenerationRequest) -> LyricsGenerationResult:
        started_at = time.perf_counter()
        sections = tuple(
            LyricsSection(section_type, (f"{section_type} mock line",))
            for section_type in request.structure
        )
        return LyricsGenerationResult(
            title="Mock Lyrics",
            sections=sections,
            full_text=render_sections(sections),
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
            generation_time_seconds=time.perf_counter() - started_at,
            metadata={
                "deterministic": True,
                "external_api": False,
                "additional_instructions_supported": False,
            },
        )
