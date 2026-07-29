"""Built-in local lyrics providers."""

from backend.lyrics.providers.mock import MockLyricsGenerator
from backend.lyrics.providers.template import TemplateLyricsGenerator

__all__ = ["MockLyricsGenerator", "TemplateLyricsGenerator"]
