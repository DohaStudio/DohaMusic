"""Contracts shared by lyrics providers and the service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LyricsGenerationRequest:
    topic: str
    genre: str | None
    mood: str | None
    language: str
    keywords: tuple[str, ...]
    structure: tuple[str, ...]
    target_duration_seconds: int | None
    additional_instructions: str | None
    allow_template_fallback: bool = False
    language_ratio: tuple[int, int] | None = None
    hook_phrase: str | None = None
    hook_style: str | None = None
    hook_repeat_count: int | None = None
    include_post_chorus: bool | None = None


@dataclass(frozen=True, slots=True)
class LyricsRevisionRequest:
    source_title: str | None
    source_language: str
    source_sections: tuple[LyricsSection, ...]
    source_full_text: str
    instruction: str
    preserve_structure: bool


@dataclass(frozen=True, slots=True)
class LyricsSection:
    section_type: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LyricsGenerationResult:
    title: str | None
    sections: tuple[LyricsSection, ...]
    full_text: str
    provider: str
    model_name: str
    model_version: str | None
    generation_time_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


class LyricsGenerator(Protocol):
    provider: str
    model_name: str
    model_version: str | None

    def generate(self, request: LyricsGenerationRequest) -> LyricsGenerationResult:
        """Generate a structured lyrics draft without persistence concerns."""
        ...


class RevisionCapableLyricsGenerator(LyricsGenerator, Protocol):
    def revise(self, request: LyricsRevisionRequest) -> LyricsGenerationResult:
        """Create a new structured version while preserving the source document."""
        ...
