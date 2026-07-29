"""Lyrics provider selection from validated application settings."""

from backend.core.config import Settings
from backend.lyrics.interfaces import LyricsGenerator
from backend.lyrics.providers.mock import MockLyricsGenerator
from backend.lyrics.providers.template import TemplateLyricsGenerator


def create_lyrics_generator(settings: Settings) -> LyricsGenerator:
    provider = settings.lyrics_provider.strip().lower()
    if provider == "mock":
        return MockLyricsGenerator()
    if provider == "template":
        return TemplateLyricsGenerator()
    raise ValueError(f"LYRICS_PROVIDER_NOT_SUPPORTED: {provider}")
