import type { AudioAnalysisStatusDto } from "@/types/api";

export interface AudioQualityMetrics {
  durationSeconds: number;
  sampleRate: number;
  channels: number;
  samplePeakDbfs: number | null;
  clippingDetected: boolean;
  clippingSampleCount: number;
  clippingRatio: number;
  integratedLufs: number | null;
}

export interface AudioAnalysisSummary {
  version: string;
  status: AudioAnalysisStatusDto;
  quality: AudioQualityMetrics | null;
  tempo: TempoAnalysisSummary | null;
  hook: HookAnalysisSummary | null;
  warnings: string[];
}

export type HookSelectionStrategy =
  | "energy_repetition"
  | "energy_peak"
  | "fallback_middle"
  | "unavailable";

export interface HookAnalysisSummary {
  version: string;
  status: AudioAnalysisStatusDto;
  candidate: {
    startSeconds: number;
    endSeconds: number;
    durationSeconds: number;
    confidence: number;
    selectionStrategy: HookSelectionStrategy;
  } | null;
}

export interface TempoAnalysisSummary {
  version: string;
  status: AudioAnalysisStatusDto;
  requestedBpm: number | null;
  detectedBpm: number | null;
  confidence: number | null;
  bpmError: number | null;
  absoluteBpmError: number | null;
  halfTimeCandidate: boolean;
  doubleTimeCandidate: boolean;
}

const analysisStatuses = new Set<AudioAnalysisStatusDto>([
  "NOT_REQUESTED",
  "PENDING",
  "COMPLETED",
  "PARTIAL",
  "FAILED",
  "UNSUPPORTED",
]);

export function parseAudioAnalysis(value: unknown): AudioAnalysisSummary | null {
  if (!isRecord(value)) return null;
  const candidate = isRecord(value.audio_analysis) ? value.audio_analysis : value;
  if (
    candidate.audio_analysis_version !== "1.0" ||
    !isAnalysisStatus(candidate.analysis_status) ||
    !Array.isArray(candidate.warnings) ||
    !candidate.warnings.every((warning) => typeof warning === "string")
  ) {
    return null;
  }
  const quality = parseQuality(candidate.quality);
  if (candidate.quality !== null && quality === null) return null;
  const tempo = parseTempo(candidate.tempo);
  if (candidate.tempo !== null && candidate.tempo !== undefined && tempo === null) return null;
  const hook = parseHook(candidate.hook);
  if (candidate.hook !== null && candidate.hook !== undefined && hook === null) return null;
  return {
    version: candidate.audio_analysis_version,
    status: candidate.analysis_status,
    quality,
    tempo,
    hook,
    warnings: [...candidate.warnings],
  };
}

function parseHook(value: unknown): HookAnalysisSummary | null {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return null;
  if (
    value.hook_analysis_version !== "1.0" ||
    !isAnalysisStatus(value.status) ||
    !(value.candidate === null || isRecord(value.candidate))
  ) {
    return null;
  }
  if (value.candidate === null) {
    return { version: value.hook_analysis_version, status: value.status, candidate: null };
  }
  const candidate = value.candidate;
  if (
    !isFiniteNumber(candidate.start_seconds) || candidate.start_seconds < 0 ||
    !isFiniteNumber(candidate.end_seconds) || candidate.end_seconds <= candidate.start_seconds ||
    !isFiniteNumber(candidate.duration_seconds) || candidate.duration_seconds <= 0 ||
    !isFiniteNumber(candidate.confidence) || candidate.confidence < 0 || candidate.confidence > 1 ||
    !isHookSelectionStrategy(candidate.selection_strategy)
  ) {
    return null;
  }
  return {
    version: value.hook_analysis_version,
    status: value.status,
    candidate: {
      startSeconds: candidate.start_seconds,
      endSeconds: candidate.end_seconds,
      durationSeconds: candidate.duration_seconds,
      confidence: candidate.confidence,
      selectionStrategy: candidate.selection_strategy,
    },
  };
}

function isHookSelectionStrategy(value: unknown): value is HookSelectionStrategy {
  return value === "energy_repetition" || value === "energy_peak" ||
    value === "fallback_middle" || value === "unavailable";
}

export function analysisConfidenceLabel(confidence: number | null): string {
  if (confidence === null) return "Unavailable";
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

function parseTempo(value: unknown): TempoAnalysisSummary | null {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return null;
  if (
    value.version !== "1.0" ||
    !isAnalysisStatus(value.status) ||
    !isNullablePositiveNumber(value.requested_bpm) ||
    !isNullablePositiveNumber(value.detected_bpm) ||
    !isNullableFiniteNumber(value.confidence) ||
    (value.confidence !== null && (value.confidence < 0 || value.confidence > 1)) ||
    !isNullableFiniteNumber(value.bpm_error) ||
    !isNullableFiniteNumber(value.absolute_bpm_error) ||
    (value.absolute_bpm_error !== null && value.absolute_bpm_error < 0) ||
    typeof value.half_time_candidate !== "boolean" ||
    typeof value.double_time_candidate !== "boolean"
  ) {
    return null;
  }
  return {
    version: value.version,
    status: value.status,
    requestedBpm: value.requested_bpm,
    detectedBpm: value.detected_bpm,
    confidence: value.confidence,
    bpmError: value.bpm_error,
    absoluteBpmError: value.absolute_bpm_error,
    halfTimeCandidate: value.half_time_candidate,
    doubleTimeCandidate: value.double_time_candidate,
  };
}

export function tempoConfidenceLabel(confidence: number | null): string {
  return analysisConfidenceLabel(confidence);
}

function parseQuality(value: unknown): AudioQualityMetrics | null {
  if (value === null) return null;
  if (!isRecord(value)) return null;
  if (
    !isFiniteNumber(value.duration_seconds) ||
    value.duration_seconds <= 0 ||
    !isFiniteNumber(value.sample_rate) ||
    value.sample_rate <= 0 ||
    !isFiniteNumber(value.channels) ||
    ![1, 2].includes(value.channels) ||
    !isFiniteNumber(value.clipping_sample_count) ||
    value.clipping_sample_count < 0 ||
    !isFiniteNumber(value.clipping_ratio) ||
    value.clipping_ratio < 0 ||
    value.clipping_ratio > 1 ||
    !isNullableFiniteNumber(value.sample_peak_dbfs) ||
    !isNullableFiniteNumber(value.integrated_lufs) ||
    typeof value.clipping_detected !== "boolean"
  ) {
    return null;
  }
  return {
    durationSeconds: value.duration_seconds,
    sampleRate: value.sample_rate,
    channels: value.channels,
    samplePeakDbfs: value.sample_peak_dbfs,
    clippingDetected: value.clipping_detected,
    clippingSampleCount: value.clipping_sample_count,
    clippingRatio: value.clipping_ratio,
    integratedLufs: value.integrated_lufs,
  };
}

export function formatAudioDuration(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  const remainder = rounded % 60;
  return minutes ? `${minutes}분 ${remainder.toString().padStart(2, "0")}초` : `${remainder}초`;
}

export function formatSampleRate(sampleRate: number): string {
  return sampleRate >= 1_000
    ? `${Number((sampleRate / 1_000).toFixed(1))} kHz`
    : `${sampleRate} Hz`;
}

function isAnalysisStatus(value: unknown): value is AudioAnalysisStatusDto {
  return typeof value === "string" && analysisStatuses.has(value as AudioAnalysisStatusDto);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNullableFiniteNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
}

function isNullablePositiveNumber(value: unknown): value is number | null {
  return value === null || (isFiniteNumber(value) && value > 0);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
