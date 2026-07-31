"""Compile K-POP product intent into a provider-neutral text prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.kpop.presets import KPOP_PRESET_REGISTRY, PresetRegistry

COMPILER_VERSION = "kpop-prompt-v1"
MAX_COMPILED_PROMPT_LENGTH = 1_500
SYSTEM_DEFAULT_PROMPT = "Create an original modern Korean pop song."

_ARTIST_IMITATION_PATTERNS = (
    re.compile(r"\bin\s+the\s+style\s+of\b", re.IGNORECASE),
    re.compile(r"\bsound(?:ing)?\s+like\b", re.IGNORECASE),
    re.compile(r"\bimitat(?:e|ing)\b.{0,40}\b(?:artist|singer|voice)\b", re.IGNORECASE),
    re.compile(r"(?:가수|아티스트|아이돌).{0,30}(?:처럼|같이|스타일|문체|창법)"),
    re.compile(r"\S+\s*(?:처럼|같이)\s*(?:노래|불러|목소리|창법)"),
)


class KPopPromptValidationError(ValueError):
    """Raised when a prompt cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class PromptCompilationResult:
    prompt: str
    preset_id: str
    genre: str
    compiler_version: str
    warnings: tuple[str, ...] = ()


class KPopPromptCompiler:
    """Apply system < preset < custom < explicit user prompt priority."""

    def __init__(self, registry: PresetRegistry = KPOP_PRESET_REGISTRY) -> None:
        self.registry = registry

    def compile(
        self,
        preset_id: str,
        user_prompt: str,
        *,
        custom_prompt: str | None = None,
    ) -> PromptCompilationResult:
        preset = self.registry.get(preset_id)
        explicit = self._normalize(user_prompt)
        custom = self._normalize(custom_prompt or "")
        self._reject_artist_imitation(explicit)
        self._reject_artist_imitation(custom)

        sections = [
            SYSTEM_DEFAULT_PROMPT,
            "Preset direction (use only when it does not conflict with user input):",
            preset.default_prompt,
            f"Preset mood: {preset.default_mood}. Preset energy: {preset.default_energy}.",
        ]
        if custom:
            sections.extend(["Additional user direction:", custom])
        if explicit:
            sections.extend(
                [
                    "User request (highest priority; follow this when directions conflict):",
                    explicit,
                ]
            )
        prompt = "\n\n".join(sections)
        if len(prompt) > MAX_COMPILED_PROMPT_LENGTH:
            raise KPopPromptValidationError(
                "Compiled K-POP prompt exceeds 1500 characters"
            )
        return PromptCompilationResult(
            prompt=prompt,
            preset_id=preset.id,
            genre=preset.genre,
            compiler_version=COMPILER_VERSION,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _reject_artist_imitation(value: str) -> None:
        if value and any(
            pattern.search(value) for pattern in _ARTIST_IMITATION_PATTERNS
        ):
            raise KPopPromptValidationError(
                "Specific artist, voice, or writing-style imitation is not supported"
            )
