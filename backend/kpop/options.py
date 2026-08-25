"""Validated provider-neutral K-POP generation options."""

from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.kpop.presets import PresetDefinition

KPopPresetId = Literal["kpop_dance", "kpop_easy_listening", "kpop_performance"]
HookStyle = Literal["title_repeat", "chant"]
VocalEnergy = Literal["low", "medium", "high"]


class StrictOptionsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LanguageRatio(StrictOptionsModel):
    ko: int = Field(ge=0, le=100)
    en: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def require_complete_ratio(self) -> LanguageRatio:
        if self.ko + self.en != 100:
            raise ValueError("Korean and English ratios must total 100")
        return self


class HookOptions(StrictOptionsModel):
    phrase: str = Field(min_length=1, max_length=40)
    style: HookStyle = "title_repeat"
    repeat_count: int = Field(default=2, ge=1, le=6)

    @field_validator("phrase")
    @classmethod
    def normalize_phrase(cls, value: str) -> str:
        return _normalize_limited_text(value, "Hook phrase")


class KPopGenerationOptions(StrictOptionsModel):
    preset_id: KPopPresetId
    requested_bpm: int | None = Field(default=None, ge=70, le=180)
    language_ratio: LanguageRatio | None = None
    hook: HookOptions | None = None
    include_post_chorus: bool | None = None
    include_dance_break: bool | None = None
    vocal_energy: VocalEnergy | None = None
    concept: str | None = Field(default=None, max_length=40)

    @field_validator("concept")
    @classmethod
    def normalize_concept(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        normalized = _normalize_limited_text(value, "Concept")
        return normalized

    def with_preset_defaults(self, preset: PresetDefinition) -> KPopGenerationOptions:
        return self.model_copy(
            update={
                "requested_bpm": self.requested_bpm or preset.default_requested_bpm,
                "language_ratio": self.language_ratio
                or LanguageRatio(
                    ko=preset.default_language_ratio[0],
                    en=preset.default_language_ratio[1],
                ),
                "include_post_chorus": (
                    preset.default_include_post_chorus
                    if self.include_post_chorus is None
                    else self.include_post_chorus
                ),
                "include_dance_break": (
                    preset.default_include_dance_break
                    if self.include_dance_break is None
                    else self.include_dance_break
                ),
                "vocal_energy": self.vocal_energy or preset.default_vocal_energy,
                "concept": self.concept or preset.default_concept,
            }
        )


def public_generation_metadata(
    snapshot: object,
) -> tuple[dict[str, object] | None, str | None]:
    """Return only validated public K-POP fields from an internal snapshot."""
    if not isinstance(snapshot, dict):
        return None, None
    raw_options = snapshot.get("normalized_generation_options")
    if raw_options is None:
        raw_options = snapshot.get("generation_options")
    try:
        options = KPopGenerationOptions.model_validate(raw_options)
    except (TypeError, ValueError):
        return None, None
    version = snapshot.get("compiler_version")
    return options.model_dump(mode="json"), version if isinstance(version, str) else None


def _normalize_limited_text(value: str, label: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{label} must not contain control characters")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    return normalized
