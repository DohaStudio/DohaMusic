"""Provider-neutral K-POP preset definitions and registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PresetDefinition:
    id: str
    display_name: str
    description: str
    genre: str
    default_prompt: str
    default_mood: str
    default_energy: str
    default_requested_bpm: int
    default_language_ratio: tuple[int, int]
    default_include_post_chorus: bool
    default_include_dance_break: bool
    default_vocal_energy: str
    default_concept: str


_PRESET_DEFINITIONS = (
    PresetDefinition(
        id="kpop_dance",
        display_name="K-POP Dance",
        description="밝고 세련된 리듬과 힘 있는 후렴을 중심으로 한 댄스 팝",
        genre="kpop_dance",
        default_prompt=(
            "Modern Korean dance pop with bright polished synth layers, rhythmic "
            "electronic drums, a rising pre-chorus, and an energetic chorus with "
            "clear Korean pronunciation."
        ),
        default_mood="bright, confident",
        default_energy="high",
        default_requested_bpm=124,
        default_language_ratio=(70, 30),
        default_include_post_chorus=True,
        default_include_dance_break=False,
        default_vocal_energy="medium",
        default_concept="confident_bright",
    ),
    PresetDefinition(
        id="kpop_easy_listening",
        display_name="K-POP Easy Listening",
        description="따뜻하고 편안한 질감과 자연스러운 반복을 살린 소프트 팝",
        genre="kpop_easy_listening",
        default_prompt=(
            "Soft modern Korean pop with warm synth textures, restrained drums, "
            "a smooth song structure, a comfortable repeated chorus, and a close "
            "natural vocal delivery."
        ),
        default_mood="warm, fresh",
        default_energy="medium",
        default_requested_bpm=104,
        default_language_ratio=(80, 20),
        default_include_post_chorus=True,
        default_include_dance_break=False,
        default_vocal_energy="low",
        default_concept="warm_fresh",
    ),
    PresetDefinition(
        id="kpop_performance",
        display_name="K-POP Performance",
        description="강한 대비와 무대 에너지를 강조한 퍼포먼스 팝",
        genre="kpop_performance",
        default_prompt=(
            "High-energy Korean performance pop with bold electronic bass, strong "
            "rhythmic drums, a tense rising pre-chorus, a chant-like hook, and a "
            "powerful chorus."
        ),
        default_mood="bold, intense",
        default_energy="high",
        default_requested_bpm=142,
        default_language_ratio=(60, 40),
        default_include_post_chorus=True,
        default_include_dance_break=True,
        default_vocal_energy="high",
        default_concept="bold_performance",
    ),
)

DEFAULT_KPOP_PRESET_ID = "kpop_dance"


class PresetRegistry:
    """Read-only registry that has no knowledge of a music provider."""

    def __init__(self, definitions: tuple[PresetDefinition, ...]) -> None:
        by_id = {definition.id: definition for definition in definitions}
        if len(by_id) != len(definitions):
            raise ValueError("K-POP preset id must be unique")
        self._definitions: Mapping[str, PresetDefinition] = MappingProxyType(by_id)

    def get(self, preset_id: str) -> PresetDefinition:
        try:
            return self._definitions[preset_id]
        except KeyError as error:
            raise ValueError(f"Unsupported K-POP preset: {preset_id}") from error

    def all(self) -> tuple[PresetDefinition, ...]:
        return tuple(self._definitions.values())


KPOP_PRESET_REGISTRY = PresetRegistry(_PRESET_DEFINITIONS)
