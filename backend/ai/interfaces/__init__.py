"""AI interface exports."""

from backend.ai.interfaces.music_generator import (
    GenerationInput,
    GenerationResult,
    MusicGenerator,
)

__all__ = ["GenerationInput", "GenerationResult", "MusicGenerator"]
from backend.ai.interfaces.stem_separator import (
    StemSeparationInput,
    StemSeparationResult,
    StemSeparator,
)

__all__ = ["StemSeparationInput", "StemSeparationResult", "StemSeparator"]
