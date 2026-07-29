"""Provider-neutral lyrics generation and validation module."""

from backend.lyrics.interfaces import (
    LyricsGenerationRequest,
    LyricsGenerationResult,
    LyricsGenerator,
    LyricsSection,
)

__all__ = [
    "LyricsGenerationRequest",
    "LyricsGenerationResult",
    "LyricsGenerator",
    "LyricsSection",
]
