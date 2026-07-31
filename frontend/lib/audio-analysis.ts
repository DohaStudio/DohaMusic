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
  warnings: string[];
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
  return {
    version: candidate.audio_analysis_version,
    status: candidate.analysis_status,
    quality,
    warnings: [...candidate.warnings],
  };
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
