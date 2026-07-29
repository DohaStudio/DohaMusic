"""Deterministic local template provider without an external LLM."""

from __future__ import annotations

import time

from backend.lyrics.interfaces import (
    LyricsGenerationRequest,
    LyricsGenerationResult,
    LyricsSection,
)
from backend.lyrics.validator import render_sections


class TemplateLyricsGenerator:
    provider = "template"
    model_name = "dohamusic-template-lyrics"
    model_version = "1.0"

    def generate(self, request: LyricsGenerationRequest) -> LyricsGenerationResult:
        started_at = time.perf_counter()
        sections = tuple(
            LyricsSection(section_type, self._lines(request, section_type, index))
            for index, section_type in enumerate(request.structure, start=1)
        )
        title = self._title(request)
        return LyricsGenerationResult(
            title=title,
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
                "quality_status": "template_draft",
            },
        )

    def _title(self, request: LyricsGenerationRequest) -> str:
        if request.language == "ko":
            return f"{request.topic[:30]}의 노래"
        return f"A Song of {request.topic[:30]}"

    def _lines(
        self,
        request: LyricsGenerationRequest,
        section_type: str,
        index: int,
    ) -> tuple[str, ...]:
        keyword = (
            request.keywords[(index - 1) % len(request.keywords)]
            if request.keywords
            else request.topic
        )
        topic = request.topic[:40]
        keyword = keyword[:30]
        mood = (request.mood or ("담담한" if request.language == "ko" else "gentle"))[
            :30
        ]
        genre = (request.genre or ("노래" if request.language == "ko" else "song"))[:30]
        if request.language == "ko":
            return self._korean_lines(section_type, topic, keyword, mood, genre)
        return self._english_lines(section_type, topic, keyword, mood, genre)

    @staticmethod
    def _korean_lines(
        section_type: str, topic: str, keyword: str, mood: str, genre: str
    ) -> tuple[str, ...]:
        if section_type in {"chorus", "final_chorus"}:
            return (
                f"{keyword}처럼 다시 번지는 {topic}",
                f"우리의 {mood} 마음을 이 {genre}에 담아",
            )
        if section_type == "bridge":
            return (f"멀어진 시간 너머 {keyword}을 따라", f"새로운 {topic}을 바라봐")
        if section_type == "outro":
            return (f"마지막 {keyword} 곁에 {topic}을 남겨",)
        return (f"{mood} 바람 속에 {keyword}이 머물고", f"오늘의 {topic}을 천천히 불러")

    @staticmethod
    def _english_lines(
        section_type: str, topic: str, keyword: str, mood: str, genre: str
    ) -> tuple[str, ...]:
        if section_type in {"chorus", "final_chorus"}:
            return (
                f"Like {keyword}, the memory of {topic} returns",
                f"We carry this {mood} heart inside the {genre}",
            )
        if section_type == "bridge":
            return (
                f"Beyond the hours I follow {keyword}",
                f"I find a new way toward {topic}",
            )
        if section_type == "outro":
            return (f"I leave {topic} beside the final {keyword}",)
        return (f"A {mood} wind keeps {keyword} near", f"Tonight I sing of {topic}")
