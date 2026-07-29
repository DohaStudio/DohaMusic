"""Lyrics provider selection from validated application settings."""

from backend.core.config import Settings
from backend.lyrics.interfaces import LyricsGenerator
from backend.lyrics.providers.mock import MockLyricsGenerator
from backend.lyrics.providers.openai import OpenAILyricsConfig, OpenAILyricsGenerator
from backend.lyrics.providers.template import TemplateLyricsGenerator


def create_lyrics_generator(settings: Settings) -> LyricsGenerator:
    provider = settings.lyrics_provider.strip().lower()
    if provider == "mock":
        return MockLyricsGenerator()
    if provider == "template":
        return TemplateLyricsGenerator()
    if provider == "openai":
        if not settings.lyrics_api_key.strip():
            raise ValueError("LYRICS_API_KEY_MISSING: DOHAMUSIC_LYRICS_API_KEY")
        return OpenAILyricsGenerator(
            OpenAILyricsConfig(
                api_key=settings.lyrics_api_key,
                model=settings.lyrics_model,
                base_url=settings.lyrics_base_url,
                timeout_seconds=settings.lyrics_timeout_seconds,
                total_deadline_seconds=settings.lyrics_total_deadline_seconds,
                max_retries=settings.lyrics_max_retries,
                temperature=settings.lyrics_temperature,
                max_output_tokens=settings.lyrics_max_output_tokens,
                input_cost_per_million=settings.lyrics_input_cost_per_million,
                output_cost_per_million=settings.lyrics_output_cost_per_million,
                pricing_version=settings.lyrics_pricing_version,
                max_cost_per_request=settings.lyrics_max_cost_per_request,
            )
        )
    raise ValueError(f"LYRICS_PROVIDER_NOT_SUPPORTED: {provider}")
