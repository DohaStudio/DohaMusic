"""Ordered pipeline steps that depend only on provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.ai.interfaces.music_generator import GenerationInput, MusicGenerator
from backend.ai.interfaces.stem_separator import StemSeparationInput, StemSeparator
from backend.ai.interfaces.voice_converter import VoiceConversionInput, VoiceConverter
from backend.core.job_status import JobStatus
from backend.pipeline.audio import AudioExporter, AudioMixer
from backend.pipeline.context import PipelineContext
from backend.pipeline.errors import OutputError, ValidationError


class PipelineStep(Protocol):
    name: str
    status: JobStatus
    progress_percent: int

    def execute(self, context: PipelineContext) -> dict[str, Any]: ...


@dataclass(slots=True)
class GenerateMusicStep:
    generator: MusicGenerator
    name: str = "music"
    status: JobStatus = JobStatus.GENERATING
    progress_percent: int = 20

    def execute(self, context: PipelineContext) -> dict[str, Any]:
        result = self.generator.generate(
            GenerationInput(
                job_id=context.job_id,
                prompt=context.prompt,
                lyrics=context.lyrics,
                genre=context.genre,
                duration_seconds=context.duration_seconds,
                seed=context.seed,
            )
        )
        if not result.audio_path.is_file():
            raise OutputError(self.name, "Music 출력 파일이 없습니다.")
        context.music_file = result.audio_path
        context.providers[self.name] = {
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
        }
        return {
            "provider_time_seconds": result.generation_time_seconds,
            "peak_vram_mb": result.peak_vram_mb,
        }


@dataclass(slots=True)
class StemSeparationStep:
    separator: StemSeparator
    name: str = "stem"
    status: JobStatus = JobStatus.STEM_SEPARATING
    progress_percent: int = 40

    def execute(self, context: PipelineContext) -> dict[str, Any]:
        if context.music_file is None:
            raise ValidationError(self.name, "Music 단계 출력이 없습니다.")
        result = self.separator.separate(
            StemSeparationInput(job_id=context.job_id, source_path=context.music_file)
        )
        if not result.vocals_path.is_file() or not result.instrumental_path.is_file():
            raise OutputError(self.name, "Stem 출력 파일이 누락되었습니다.")
        context.vocals_file = result.vocals_path
        context.instrumental_file = result.instrumental_path
        context.providers[self.name] = {
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
        }
        return {
            "provider_time_seconds": result.separation_time_seconds,
            "peak_vram_mb": result.peak_vram_mb,
            "peak_process_memory_mb": result.peak_process_memory_mb,
        }


@dataclass(slots=True)
class VoiceConversionStep:
    converter: VoiceConverter
    name: str = "voice"
    status: JobStatus = JobStatus.VOICE_CONVERTING
    progress_percent: int = 60

    def execute(self, context: PipelineContext) -> dict[str, Any]:
        if context.vocals_file is None:
            raise ValidationError(self.name, "Stem 보컬 출력이 없습니다.")
        result = self.converter.convert(
            VoiceConversionInput(
                job_id=context.job_id,
                source_path=context.vocals_file,
                reference_path=context.reference_voice_path,
            )
        )
        if not result.converted_path.is_file():
            raise OutputError(self.name, "Voice Conversion 출력 파일이 없습니다.")
        context.converted_voice = result.converted_path
        context.providers[self.name] = {
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
        }
        return {
            "provider_time_seconds": result.conversion_time_seconds,
            "peak_vram_mb": result.peak_vram_mb,
            "peak_process_memory_mb": result.peak_process_memory_mb,
        }


@dataclass(slots=True)
class MixStep:
    mixer: AudioMixer
    name: str = "mixer"
    status: JobStatus = JobStatus.MIXING
    progress_percent: int = 80

    def execute(self, context: PipelineContext) -> dict[str, Any]:
        if context.instrumental_file is None or context.converted_voice is None:
            raise ValidationError(self.name, "Mixer 입력이 완성되지 않았습니다.")
        result = self.mixer.mix(
            context.job_id, context.instrumental_file, context.converted_voice
        )
        if not result.audio_path.is_file():
            raise OutputError(self.name, "Mixer 출력 파일이 없습니다.")
        context.mixed_file = result.audio_path
        context.providers[self.name] = {"provider": result.provider}
        return {"mock": result.provider == "mock"}


@dataclass(slots=True)
class ExportStep:
    exporter: AudioExporter
    name: str = "export"
    status: JobStatus = JobStatus.EXPORTING
    progress_percent: int = 100

    def execute(self, context: PipelineContext) -> dict[str, Any]:
        if context.mixed_file is None:
            raise ValidationError(self.name, "Mixer 출력이 없습니다.")
        context.output_file = self.exporter.export(context.job_id, context.mixed_file)
        if not context.output_file.is_file():
            raise OutputError(self.name, "Exporter 출력 파일이 없습니다.")
        context.providers[self.name] = {"provider": "wav"}
        return {"format": "wav"}
