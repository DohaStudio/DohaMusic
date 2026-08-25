from __future__ import annotations

from pathlib import Path

from backend.ai.interfaces.music_generator import GenerationResult
from backend.kpop import KPOP_PRESET_REGISTRY, KPopPromptCompiler
from backend.kpop.prompt_compiler import KPopPromptValidationError
from backend.lyrics.constants import KPOP_STRUCTURE
from backend.lyrics.interfaces import LyricsGenerationRequest
from backend.lyrics.providers.template import TemplateLyricsGenerator
from backend.pipeline.context import PipelineContext
from backend.pipeline.steps import GenerateMusicStep
from backend.schemas.lyrics import LyricsCreate


def test_preset_registry_exposes_three_provider_neutral_definitions() -> None:
    presets = KPOP_PRESET_REGISTRY.all()
    assert [preset.id for preset in presets] == [
        "kpop_dance",
        "kpop_easy_listening",
        "kpop_performance",
    ]
    assert all(preset.genre == preset.id for preset in presets)
    assert all("ace" not in preset.default_prompt.lower() for preset in presets)


def test_prompt_compiler_keeps_explicit_user_request_at_highest_priority() -> None:
    result = KPopPromptCompiler().compile(
        "kpop_dance",
        "여름 느낌의 자신감 있는 곡",
        custom_prompt="Mood: refreshing",
    )
    assert result.genre == "kpop_dance"
    assert result.compiler_version == "kpop-prompt-v1"
    assert result.prompt.index("Preset direction") < result.prompt.index(
        "Additional user direction"
    )
    assert result.prompt.index("Additional user direction") < result.prompt.index(
        "User request (highest priority"
    )
    assert result.prompt.endswith("여름 느낌의 자신감 있는 곡")


def test_prompt_compiler_rejects_artist_imitation() -> None:
    try:
        KPopPromptCompiler().compile("kpop_dance", "유명 가수처럼 노래해 줘")
    except KPopPromptValidationError:
        pass
    else:
        raise AssertionError("artist imitation must be rejected")


def test_kpop_lyrics_request_uses_k0_structure_and_template_rules() -> None:
    payload = LyricsCreate(topic="우리의 여름", genre="kpop_dance")
    assert tuple(payload.structure) == KPOP_STRUCTURE
    request = LyricsGenerationRequest(
        topic=payload.topic,
        genre=payload.genre,
        mood="밝은",
        language="ko",
        keywords=("여름",),
        structure=tuple(payload.structure),
        target_duration_seconds=60,
        additional_instructions=None,
    )
    result = TemplateLyricsGenerator().generate(request)
    assert [section.section_type for section in result.sections] == list(KPOP_STRUCTURE)
    chorus = next(section for section in result.sections if section.section_type == "chorus")
    post_chorus = next(
        section for section in result.sections if section.section_type == "post_chorus"
    )
    bridge = next(section for section in result.sections if section.section_type == "bridge")
    assert sum(line.count("여름") for line in chorus.lines) >= 2
    assert all(len(line) < 40 for line in post_chorus.lines)
    assert "새로운 마음" in " ".join(bridge.lines)
    assert result.metadata["lyrics_template"] == "kpop_v1"


class RecordingMusicGenerator:
    model_name = "recording"

    def __init__(self) -> None:
        self.output_path = Path(__file__)
        self.request = None

    def generate(self, request):
        self.request = request
        return GenerationResult(
            audio_path=self.output_path,
            provider="recording",
            model_name=self.model_name,
            model_version="1",
            seed=request.seed,
            duration_seconds=float(request.duration_seconds),
            generation_time_seconds=0.0,
            peak_vram_mb=None,
            file_type="wav",
        )


def test_compiled_prompt_flows_through_existing_music_generator_contract() -> None:
    compiled = KPopPromptCompiler().compile("kpop_performance", "강한 무대 대비")
    generator = RecordingMusicGenerator()
    context = PipelineContext(
        job_id="kpop-regression",
        prompt=compiled.prompt,
        lyrics=None,
        genre=compiled.genre,
        duration_seconds=30,
        seed=7,
        voice_profile_id="profile",
        reference_voice_path=Path(__file__),
        pipeline_version="test",
    )

    GenerateMusicStep(generator).execute(context)

    assert generator.request.prompt == compiled.prompt
    assert generator.request.genre == "kpop_performance"
    assert not hasattr(generator.request, "preset_id")
