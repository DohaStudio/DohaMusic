import { ApiError } from "@/services/api-client";
import type {
  VoiceEnrollmentDto,
  VoiceEnrollmentSampleDto,
  VoiceEnrollmentSession,
  VoiceEnrollmentStatus,
  VoiceEnrollmentStep,
  VoiceQualityStatus,
  VoiceSampleSourceType,
  VoiceSampleStatus,
} from "./voice-enrollment-types";
import {
  MAX_VOICE_DURATION_SECONDS,
  MAX_VOICE_SAMPLE_BYTES,
  MIN_VOICE_DURATION_SECONDS,
} from "./voice-enrollment-types";

const ENROLLMENT_STATUSES = new Set<VoiceEnrollmentStatus>([
  "DRAFT", "READY_TO_SUBMIT", "SUBMITTING", "COMPLETED", "FAILED",
  "CANCELLED", "EXPIRED", "DELETE_PENDING", "DELETE_FAILED",
]);
const SAMPLE_STATUSES = new Set<VoiceSampleStatus>([
  "UPLOADED", "VALIDATING", "READY", "FAILED", "PROMOTED",
  "DELETE_PENDING", "DELETE_FAILED", "DELETED",
]);
const QUALITY_STATUSES = new Set<VoiceQualityStatus>(["PASS", "WARNING", "FAIL"]);
const SOURCE_TYPES = new Set<VoiceSampleSourceType>(["BROWSER_RECORDING", "FILE_UPLOAD"]);
const STEPS = new Set<VoiceEnrollmentStep>([
  "guide", "consent", "method", "samples", "quality", "reference", "review", "complete",
]);

type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue =>
  value !== null && typeof value === "object" ? value as RecordValue : {};
const string = (value: unknown, fallback = ""): string =>
  typeof value === "string" ? value : fallback;
const nullableString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const number = (value: unknown, fallback = 0): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;
const nullableNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const stringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

export function mapVoiceSampleDto(value: unknown): VoiceEnrollmentSampleDto {
  const source = record(value);
  const quality = record(source.quality);
  const qualityStatus = string(quality.status);
  const sampleStatus = string(source.status);
  const sourceType = string(source.source_type);
  return {
    id: string(source.id),
    enrollment_id: nullableString(source.enrollment_id),
    source_type: SOURCE_TYPES.has(sourceType as VoiceSampleSourceType)
      ? sourceType as VoiceSampleSourceType : "FILE_UPLOAD",
    prompt_id: nullableString(source.prompt_id),
    category: string(source.category, "BASIC_SPEECH"),
    status: SAMPLE_STATUSES.has(sampleStatus as VoiceSampleStatus)
      ? sampleStatus as VoiceSampleStatus : "FAILED",
    original_content_type: nullableString(source.original_content_type),
    original_size_bytes: nullableNumber(source.original_size_bytes),
    normalized_content_type: nullableString(source.normalized_content_type),
    normalized_size_bytes: nullableNumber(source.normalized_size_bytes),
    duration_seconds: nullableNumber(source.duration_seconds),
    sample_rate: nullableNumber(source.sample_rate),
    channels: nullableNumber(source.channels),
    bit_depth: nullableNumber(source.bit_depth),
    quality: {
      status: QUALITY_STATUSES.has(qualityStatus as VoiceQualityStatus)
        ? qualityStatus as VoiceQualityStatus : "FAIL",
      warnings: stringArray(quality.warnings),
      version: nullableString(quality.version),
      peak: nullableNumber(quality.peak),
      rms: nullableNumber(quality.rms),
      silence_ratio: nullableNumber(quality.silence_ratio),
      clipping_ratio: nullableNumber(quality.clipping_ratio),
    },
    failure_code: nullableString(source.failure_code),
    submit_eligible: source.submit_eligible === true,
    cleanup_status: string(source.cleanup_status, "NOT_REQUESTED"),
    created_at: string(source.created_at),
    validated_at: nullableString(source.validated_at),
  };
}

export function mapVoiceEnrollmentDto(value: unknown): VoiceEnrollmentDto {
  const source = record(value);
  const status = string(source.status);
  const summary = record(source.validation_summary);
  return {
    id: string(source.id),
    status: ENROLLMENT_STATUSES.has(status as VoiceEnrollmentStatus)
      ? status as VoiceEnrollmentStatus : "FAILED",
    name: string(source.name),
    description: nullableString(source.description),
    consent_confirmed: source.consent_confirmed === true,
    consent_policy_version: nullableString(source.consent_policy_version),
    sample_count: number(source.sample_count),
    samples: Array.isArray(source.samples) ? source.samples.map(mapVoiceSampleDto) : [],
    can_submit: source.can_submit === true,
    validation_summary: {
      ready: number(summary.ready), warning: number(summary.warning), failed: number(summary.failed),
    },
    cleanup_status: string(source.cleanup_status, "NOT_REQUESTED"),
    cleanup_failure_code: nullableString(source.cleanup_failure_code),
    voice_profile_id: nullableString(source.voice_profile_id),
    created_at: string(source.created_at),
    updated_at: string(source.updated_at),
    expires_at: nullableString(source.expires_at),
    absolute_expires_at: nullableString(source.absolute_expires_at),
  };
}

export const MEDIA_RECORDER_MIME_PRIORITY = [
  "audio/wav", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg",
] as const;

export function selectMediaRecorderMime(
  isSupported: (mime: string) => boolean,
): string | undefined {
  return MEDIA_RECORDER_MIME_PRIORITY.find((mime) => isSupported(mime));
}

export function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function validateEnrollmentFile(file: File): string | undefined {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!file.size) return "빈 파일은 등록할 수 없습니다.";
  if (file.size > MAX_VOICE_SAMPLE_BYTES) return "파일은 25MB 이하여야 합니다.";
  if (!extension || !["wav", "webm", "ogg"].includes(extension)) {
    return "WAV, WebM 또는 Ogg 음성 파일을 선택해 주세요.";
  }
  return undefined;
}

export function validateRecordingDuration(seconds: number): string | undefined {
  if (seconds < MIN_VOICE_DURATION_SECONDS) return "음성은 5초 이상 녹음해 주세요.";
  if (seconds > MAX_VOICE_DURATION_SECONDS) return "음성은 60초 이하여야 합니다.";
  return undefined;
}

const QUALITY_MESSAGES: Record<string, string> = {
  LOW_VOLUME: "목소리가 작게 녹음되었습니다. 더 가까운 거리에서 다시 녹음하면 결과가 좋아질 수 있습니다.",
  HIGH_SILENCE_RATIO: "목소리가 들리지 않는 구간이 많습니다. 말하는 구간을 조금 더 늘려 주세요.",
  POSSIBLE_CLIPPING: "일부 구간의 음량이 너무 커서 소리가 찌그러졌을 수 있습니다.",
};
export function qualityWarningMessage(code: string): string {
  return QUALITY_MESSAGES[code] ?? "기본 품질 경고가 있습니다. 샘플을 확인해 주세요.";
}

const ENROLLMENT_ERROR_MESSAGES: Record<string, string> = {
  VOICE_ENROLLMENT_NOT_FOUND: "음성 등록 작업을 찾을 수 없습니다. 새 등록을 시작해 주세요.",
  VOICE_ENROLLMENT_EXPIRED: "음성 등록 시간이 만료되었습니다. 새 등록을 시작해 주세요.",
  VOICE_ENROLLMENT_INVALID_STATE: "현재 단계에서는 이 작업을 할 수 없습니다. 상태를 새로 확인해 주세요.",
  VOICE_ENROLLMENT_ALREADY_SUBMITTED: "이미 등록된 목소리입니다. 목소리 목록을 확인해 주세요.",
  VOICE_SAMPLE_NOT_FOUND: "음성 샘플을 찾을 수 없습니다. 목록을 새로 확인해 주세요.",
  VOICE_SAMPLE_LIMIT_EXCEEDED: "최대 10개의 음성 샘플만 등록할 수 있습니다.",
  VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE: "지원하는 WAV, WebM 또는 Ogg 음성 파일을 사용해 주세요.",
  VOICE_SAMPLE_TOO_LARGE: "음성 파일은 25MB 이하여야 합니다.",
  VOICE_SAMPLE_DURATION_TOO_SHORT: "음성은 5초 이상이어야 합니다.",
  VOICE_SAMPLE_DURATION_TOO_LONG: "음성은 60초 이하여야 합니다.",
  VOICE_SAMPLE_DECODE_FAILED: "음성 파일을 읽지 못했습니다. 다시 녹음하거나 다른 파일을 선택해 주세요.",
  VOICE_SAMPLE_UNSUPPORTED_CODEC: "이 WAV 파일의 오디오 형식은 지원하지 않습니다. PCM 16-bit WAV로 변환해 주세요.",
  VOICE_SAMPLE_NORMALIZATION_FAILED: "음성 형식을 준비하지 못했습니다. 같은 파일로 다시 시도해 주세요.",
  VOICE_SAMPLE_VALIDATION_FAILED: "이 음성 샘플은 등록 조건을 충족하지 않습니다.",
  VOICE_SAMPLE_IN_USE: "등록 처리 중이거나 사용 중인 샘플은 삭제할 수 없습니다.",
  VOICE_CONSENT_REQUIRED: "음성 처리와 보관 범위에 동의해 주세요.",
  VOICE_PROFILE_CREATION_FAILED: "목소리 프로필을 만들지 못했습니다. 상태를 확인한 뒤 다시 시도해 주세요.",
  VOICE_CLEANUP_PENDING: "음성 파일 삭제가 진행 중입니다. 잠시 후 상태를 다시 확인해 주세요.",
  VOICE_CLEANUP_FAILED: "음성 파일을 안전하게 삭제하지 못했습니다. 상태를 다시 확인해 주세요.",
  IDEMPOTENCY_KEY_REQUIRED: "요청을 안전하게 처리할 수 없습니다. 새로고침 후 다시 시도해 주세요.",
  IDEMPOTENCY_CONFLICT: "이 요청의 내용이 변경되었습니다. 새 작업으로 다시 시도해 주세요.",
  VOICE_NORMALIZER_UNAVAILABLE: "현재 서버에서는 이 녹음 형식을 처리할 수 없습니다. WAV 파일을 업로드해 주세요.",
  REQUEST_TIMEOUT: "서버 응답이 지연되고 있습니다. 상태를 확인한 뒤 같은 작업을 다시 시도해 주세요.",
  NETWORK_ERROR: "음성 등록 서버에 연결할 수 없습니다. 연결을 확인한 뒤 다시 시도해 주세요.",
};

export function voiceEnrollmentErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return ENROLLMENT_ERROR_MESSAGES[error.code] ?? error.message;
  }
  return "음성 등록 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function shouldClearEnrollmentSession(error: unknown): boolean {
  return error instanceof ApiError && [
    "VOICE_ENROLLMENT_NOT_FOUND", "VOICE_ENROLLMENT_EXPIRED",
  ].includes(error.code);
}

export function readEnrollmentSession(storage: Storage): VoiceEnrollmentSession | null {
  try {
    const value = JSON.parse(storage.getItem("doha.voice-enrollment.v1") ?? "null") as unknown;
    const source = record(value);
    const enrollmentId = string(source.enrollmentId);
    const step = string(source.step);
    if (!enrollmentId || !STEPS.has(step as VoiceEnrollmentStep)) return null;
    return { enrollmentId, step: step as VoiceEnrollmentStep };
  } catch {
    return null;
  }
}

export function writeEnrollmentSession(storage: Storage, value: VoiceEnrollmentSession): void {
  storage.setItem("doha.voice-enrollment.v1", JSON.stringify(value));
}
