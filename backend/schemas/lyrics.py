"""Lyrics API request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.lyrics.constants import (
    DEFAULT_STRUCTURE,
    MAX_INSTRUCTIONS_LENGTH,
    MAX_KEYWORD_LENGTH,
    MAX_KEYWORDS,
    MAX_RAW_LYRICS_LENGTH,
    MAX_STRUCTURE_ITEMS,
    MAX_TARGET_DURATION_SECONDS,
    MAX_TOPIC_LENGTH,
    MIN_TARGET_DURATION_SECONDS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_SECTION_TYPES,
)
from backend.lyrics.validator import normalize_plain_text, normalize_section_type


class LyricsCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=MAX_TOPIC_LENGTH)
    genre: str | None = Field(default=None, max_length=100)
    mood: str | None = Field(default=None, max_length=100)
    language: str = "ko"
    keywords: list[str] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    structure: list[str] = Field(
        default_factory=lambda: list(DEFAULT_STRUCTURE), max_length=MAX_STRUCTURE_ITEMS
    )
    target_duration_seconds: int | None = Field(
        default=None,
        ge=MIN_TARGET_DURATION_SECONDS,
        le=MAX_TARGET_DURATION_SECONDS,
    )
    additional_instructions: str | None = Field(
        default=None, max_length=MAX_INSTRUCTIONS_LENGTH
    )

    @field_validator("topic", "genre", "mood", "additional_instructions")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_plain_text(value)
        return normalized or None

    @field_validator("topic")
    @classmethod
    def require_topic(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("topic is required")
        return value

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("unsupported language")
        return normalized

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, values: list[str]) -> list[str]:
        normalized = [normalize_plain_text(value) for value in values]
        if any(not value or len(value) > MAX_KEYWORD_LENGTH for value in normalized):
            raise ValueError("invalid keyword")
        return list(dict.fromkeys(normalized))

    @field_validator("structure")
    @classmethod
    def normalize_structure(cls, values: list[str]) -> list[str]:
        normalized = [normalize_section_type(value) for value in values]
        if not normalized or any(
            value not in SUPPORTED_SECTION_TYPES for value in normalized
        ):
            raise ValueError("invalid structure")
        return normalized


class LyricsValidationRequest(BaseModel):
    raw_lyrics: str = Field(min_length=1, max_length=MAX_RAW_LYRICS_LENGTH)
    language: str = "ko"

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("unsupported language")
        return normalized


class LyricsSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_type: str
    lines: list[str]


class LyricsValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid: bool
    normalized_lyrics: str
    sections: list[LyricsSectionRead]
    warnings: list[str]
    errors: list[str]
    character_count: int
    line_count: int
    section_count: int
    repetition_ratio: float


class LyricsDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    language: str
    topic: str
    genre: str | None
    mood: str | None
    keywords: list[str]
    structure: list[str]
    sections: list[LyricsSectionRead] = Field(validation_alias="sections_data")
    full_text: str
    provider: str
    model_name: str
    model_version: str | None
    status: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_payload")
    created_at: datetime
    updated_at: datetime
