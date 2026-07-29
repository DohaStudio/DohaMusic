"""Audio mixer provider selection."""

from pathlib import Path

from backend.audio.config import AudioMixerConfig
from backend.audio.default_mixer import DefaultAudioMixer
from backend.audio.interfaces import AudioMixer
from backend.audio.mock_mixer import MockAudioMixer
from backend.core.config import Settings


def create_audio_mixer(settings: Settings, output_root: Path) -> AudioMixer:
    provider = settings.audio_mixer.strip().lower()
    if provider == "mock":
        return MockAudioMixer(output_root)
    if provider == "default":
        return DefaultAudioMixer(
            AudioMixerConfig(
                output_root=str(output_root),
                vocal_gain_db=settings.mixer_vocal_gain_db,
                instrumental_gain_db=settings.mixer_instrumental_gain_db,
                headroom_db=settings.mixer_headroom_db,
                normalization=settings.mixer_normalization,
                limiter=settings.mixer_limiter,
                fade_in_ms=settings.mixer_fade_in_ms,
                fade_out_ms=settings.mixer_fade_out_ms,
            )
        )
    raise ValueError(f"Unsupported audio mixer provider: {settings.audio_mixer}")
