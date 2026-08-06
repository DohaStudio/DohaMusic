"""Versioned internal and public contracts for final-mix quality analysis."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

AUDIO_ANALYSIS_VERSION = "1.0"
PUBLIC_WARNING_MESSAGES = {
    "SILENT_AUDIO": "오디오가 무음이라 최대 음량을 계산할 수 없습니다.",
    "CLIPPING_DETECTED": "일부 구간에서 소리가 과도하게 커 왜곡될 수 있습니다.",
    "LUFS_UNAVAILABLE": "통합 음량을 분석하지 못했습니다.",
    "UNSUPPORTED_CHANNELS": "현재 채널 구성은 품질 분석을 지원하지 않습니다.",
    "UNSUPPORTED_AUDIO_FORMAT": "현재 오디오 형식은 품질 분석을 지원하지 않습니다.",
    "INVALID_AUDIO_DATA": "유효한 오디오 데이터가 없어 품질을 분석하지 못했습니다.",
    "AUDIO_DECODE_FAILED": "오디오 파일을 읽지 못해 품질을 분석하지 못했습니다.",
    "ANALYSIS_INTERNAL_ERROR": "오디오 품질 분석을 완료하지 못했습니다.",
    "TEMPO_AUDIO_TOO_SHORT": "템포를 추정하기에 오디오 길이가 충분하지 않습니다.",
    "TEMPO_SILENT_AUDIO": "무음 오디오에서는 템포를 추정할 수 없습니다.",
    "TEMPO_DETECTION_FAILED": "템포를 안정적으로 추정하지 못했습니다.",
    "TEMPO_CONFIDENCE_LOW": "템포 추정 신뢰도가 낮아 참고용으로만 제공됩니다.",
    "TEMPO_UNSUPPORTED_AUDIO": "현재 오디오 형식은 템포 분석을 지원하지 않습니다.",
    "HOOK_AUDIO_TOO_SHORT": "곡이 짧아 전체 구간을 후렴 대체 후보로 제공합니다.",
    "HOOK_SILENT_AUDIO": "무음 오디오에서는 후렴 후보를 추정할 수 없습니다.",
    "HOOK_DETECTION_FAILED": "후렴 후보를 안정적으로 추정하지 못했습니다.",
    "HOOK_FALLBACK_MIDDLE": "후렴 후보 신뢰도가 낮아 곡 중앙 구간을 대체 후보로 제공합니다.",
    "HOOK_UNSUPPORTED_AUDIO": "현재 오디오 형식은 후렴 후보 분석을 지원하지 않습니다.",
}


class AudioAnalysisStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class AudioAnalysisWarning(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=300)


class AudioQualityMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    duration_seconds: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(ge=1, le=2)
    sample_peak_dbfs: float | None
    clipping_detected: bool
    clipping_sample_count: int = Field(ge=0)
    clipping_ratio: float = Field(ge=0, le=1)
    integrated_lufs: float | None


class TempoAnalysisResult(BaseModel):
    """Internal tempo result. Diagnostic details stay outside the public DTO."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    version: str = "1.0"
    status: AudioAnalysisStatus
    requested_bpm: float | None = Field(default=None, gt=0)
    detected_bpm: float | None = Field(default=None, gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    bpm_error: float | None = None
    absolute_bpm_error: float | None = Field(default=None, ge=0)
    half_time_candidate: bool = False
    double_time_candidate: bool = False
    warnings: list[AudioAnalysisWarning] = Field(default_factory=list)

    @classmethod
    def pending(cls, requested_bpm: float | None) -> TempoAnalysisResult:
        return cls(status=AudioAnalysisStatus.PENDING, requested_bpm=requested_bpm)

    @classmethod
    def failed(
        cls,
        requested_bpm: float | None,
        warning: AudioAnalysisWarning,
        *,
        unsupported: bool = False,
    ) -> TempoAnalysisResult:
        return cls(
            status=(
                AudioAnalysisStatus.UNSUPPORTED
                if unsupported
                else AudioAnalysisStatus.FAILED
            ),
            requested_bpm=requested_bpm,
            warnings=[warning],
        )


class HookSelectionStrategy(StrEnum):
    ENERGY_REPETITION = "energy_repetition"
    ENERGY_PEAK = "energy_peak"
    FALLBACK_MIDDLE = "fallback_middle"
    UNAVAILABLE = "unavailable"


class HookCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    selection_strategy: HookSelectionStrategy

    @model_validator(mode="after")
    def validate_window(self) -> HookCandidate:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Hook candidate end must follow start")
        expected_duration = self.end_seconds - self.start_seconds
        if not math.isclose(self.duration_seconds, expected_duration, abs_tol=0.01):
            raise ValueError("Hook candidate duration must match its window")
        return self


class HookAnalysisResult(BaseModel):
    """Internal Hook candidate result; never an exact Chorus assertion."""

    model_config = ConfigDict(extra="ignore")

    hook_analysis_version: str = "1.0"
    status: AudioAnalysisStatus
    candidate: HookCandidate | None = None
    warnings: list[AudioAnalysisWarning] = Field(default_factory=list)

    @classmethod
    def pending(cls) -> HookAnalysisResult:
        return cls(status=AudioAnalysisStatus.PENDING)

    @classmethod
    def failed(
        cls,
        warning: AudioAnalysisWarning,
        *,
        unsupported: bool = False,
    ) -> HookAnalysisResult:
        return cls(
            status=(
                AudioAnalysisStatus.UNSUPPORTED
                if unsupported
                else AudioAnalysisStatus.FAILED
            ),
            warnings=[warning],
        )


class AudioAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    audio_analysis_version: str = AUDIO_ANALYSIS_VERSION
    analysis_status: AudioAnalysisStatus
    source_file_role: str = "final_mix"
    quality: AudioQualityMetrics | None
    tempo: TempoAnalysisResult | None = None
    hook: HookAnalysisResult | None = None
    warnings: list[AudioAnalysisWarning]

    @classmethod
    def pending(cls, requested_bpm: float | None = None) -> AudioAnalysisResult:
        return cls(
            analysis_status=AudioAnalysisStatus.PENDING,
            quality=None,
            tempo=TempoAnalysisResult.pending(requested_bpm),
            hook=HookAnalysisResult.pending(),
            warnings=[],
        )

    @classmethod
    def failed(cls, requested_bpm: float | None = None) -> AudioAnalysisResult:
        warning = AudioAnalysisWarning(
            code="ANALYSIS_INTERNAL_ERROR",
            message="오디오 품질 분석을 완료하지 못했습니다.",
        )
        return cls(
            analysis_status=AudioAnalysisStatus.FAILED,
            quality=None,
            tempo=TempoAnalysisResult.failed(requested_bpm, warning),
            hook=HookAnalysisResult.failed(warning),
            warnings=[warning],
        )


class PublicAudioAnalysis(BaseModel):
    """Allowlisted API representation without paths or analyzer internals."""

    model_config = ConfigDict(extra="ignore")

    audio_analysis_version: str
    analysis_status: AudioAnalysisStatus
    quality: AudioQualityMetrics | None
    tempo: PublicTempoAnalysis | None
    hook: PublicHookAnalysis | None
    warnings: list[str]


class PublicTempoAnalysis(BaseModel):
    """Strict allowlist for public Tempo Analysis metadata."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    version: str
    status: AudioAnalysisStatus
    requested_bpm: float | None
    detected_bpm: float | None
    confidence: float | None
    bpm_error: float | None
    absolute_bpm_error: float | None
    half_time_candidate: bool
    double_time_candidate: bool


class PublicHookAnalysis(BaseModel):
    """Strict allowlist for public Hook candidate metadata."""

    model_config = ConfigDict(extra="ignore")

    hook_analysis_version: str
    status: AudioAnalysisStatus
    candidate: HookCandidate | None


PublicAudioAnalysis.model_rebuild()


def public_audio_analysis(metadata: object) -> PublicAudioAnalysis | None:
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("audio_analysis")
    if not isinstance(raw, dict):
        return None
    try:
        internal = AudioAnalysisResult.model_validate(raw)
    except ValueError:
        return None
    if internal.audio_analysis_version != AUDIO_ANALYSIS_VERSION:
        return None
    return PublicAudioAnalysis(
        audio_analysis_version=internal.audio_analysis_version,
        analysis_status=internal.analysis_status,
        quality=internal.quality,
        tempo=(
            PublicTempoAnalysis(
                version=internal.tempo.version,
                status=internal.tempo.status,
                requested_bpm=internal.tempo.requested_bpm,
                detected_bpm=internal.tempo.detected_bpm,
                confidence=internal.tempo.confidence,
                bpm_error=internal.tempo.bpm_error,
                absolute_bpm_error=internal.tempo.absolute_bpm_error,
                half_time_candidate=internal.tempo.half_time_candidate,
                double_time_candidate=internal.tempo.double_time_candidate,
            )
            if internal.tempo is not None
            else None
        ),
        hook=(
            PublicHookAnalysis(
                hook_analysis_version=internal.hook.hook_analysis_version,
                status=internal.hook.status,
                candidate=internal.hook.candidate,
            )
            if internal.hook is not None
            else None
        ),
        warnings=[
            PUBLIC_WARNING_MESSAGES[warning.code]
            for warning in internal.warnings
            if warning.code in PUBLIC_WARNING_MESSAGES
        ],
    )


def sanitize_result_metadata(metadata: object) -> dict[str, Any]:
    """Preserve existing public metadata while allowlisting audio analysis."""

    if not isinstance(metadata, dict):
        return {}
    sanitized = dict(metadata)
    analysis = public_audio_analysis(metadata)
    if analysis is None:
        sanitized.pop("audio_analysis", None)
    else:
        sanitized["audio_analysis"] = analysis.model_dump(mode="json")
    return sanitized
