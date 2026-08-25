"""Compile K-POP product intent into a provider-neutral text prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.kpop.options import KPopGenerationOptions
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
    normalized_options: KPopGenerationOptions | None = None


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
        options: KPopGenerationOptions | None = None,
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
        normalized_options = None
        if options is not None:
            if options.preset_id != preset.id:
                raise KPopPromptValidationError("Preset and options must match")
            normalized_options = options.with_preset_defaults(preset)
            sections.extend(self._option_sections(normalized_options))
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
            raise KPopPromptValidationError("Compiled K-POP prompt exceeds 1500 characters")
        return PromptCompilationResult(
            prompt=prompt,
            preset_id=preset.id,
            genre=preset.genre,
            compiler_version=COMPILER_VERSION,
            normalized_options=normalized_options,
        )

    @staticmethod
    def _option_sections(options: KPopGenerationOptions) -> list[str]:
        sections = ["Structured user options (override preset defaults):"]
        if options.requested_bpm is not None:
            sections.append(
                f"Target tempo around {options.requested_bpm} BPM; "
                "treat this as a prompt goal, not an exact guarantee."
            )
        if options.language_ratio is not None:
            sections.append(
                "Lyrics language target: "
                f"{options.language_ratio.ko}% Korean and {options.language_ratio.en}% English; "
                "do not claim an exact final ratio."
            )
        if options.hook is not None:
            style = (
                "a repeated title hook"
                if options.hook.style == "title_repeat"
                else "a chant-style hook"
            )
            sections.extend(
                [
                    f'Include {style}: "{options.hook.phrase}".',
                    f"Repeat the hook approximately {options.hook.repeat_count} times.",
                ]
            )
        sections.append(
            "Include a post-chorus."
            if options.include_post_chorus
            else "Do not include a post-chorus."
        )
        sections.append(
            "Include a dance-break contrast."
            if options.include_dance_break
            else "Do not include a dance break."
        )
        if options.vocal_energy is not None:
            sections.append(f"Use {options.vocal_energy} vocal energy.")
        if options.concept:
            sections.append(f"Concept: {options.concept}.")
        return sections

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _reject_artist_imitation(value: str) -> None:
        if value and any(pattern.search(value) for pattern in _ARTIST_IMITATION_PATTERNS):
            raise KPopPromptValidationError(
                "Specific artist, voice, or writing-style imitation is not supported"
            )
