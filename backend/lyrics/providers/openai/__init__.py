"""Experimental OpenAI lyrics provider."""

from backend.lyrics.providers.openai.adapter import OpenAILyricsGenerator
from backend.lyrics.providers.openai.config import OpenAILyricsConfig

__all__ = ["OpenAILyricsConfig", "OpenAILyricsGenerator"]
