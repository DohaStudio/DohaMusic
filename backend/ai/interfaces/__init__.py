"""AI interface exports."""

from backend.ai.interfaces.music_generator import (
    GenerationInput,
    GenerationResult,
    MusicGenerator,
)

__all__ = ["GenerationInput", "GenerationResult", "MusicGenerator"]
