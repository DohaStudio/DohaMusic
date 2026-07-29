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
