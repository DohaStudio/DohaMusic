import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/services/api-client";
import {
  createIdempotencyKey,
  formatDuration,
  mapVoiceEnrollmentDto,
  mapVoiceSampleDto,
  qualityWarningMessage,
  readEnrollmentSession,
  selectMediaRecorderMime,
  shouldClearEnrollmentSession,
  validateEnrollmentFile,
  validateRecordingDuration,
  voiceEnrollmentErrorMessage,
  writeEnrollmentSession,
} from "@/features/voice/voice-enrollment-utils";

describe("Voice Enrollment utilities", () => {
  it("브라우저가 지원하는 첫 번째 MIME을 우선순위대로 선택한다", () => {
    const supported = vi.fn((mime: string) => mime === "audio/webm");
    expect(selectMediaRecorderMime(supported)).toBe("audio/webm");
    expect(supported).toHaveBeenCalledWith("audio/wav");
    expect(selectMediaRecorderMime(() => false)).toBeUndefined();
  });

  it("녹음 시간을 mm:ss로 안전하게 표시한다", () => {
    expect(formatDuration(0)).toBe("00:00");
    expect(formatDuration(65.9)).toBe("01:05");
    expect(formatDuration(-1)).toBe("00:00");
  });

  it("5~60초와 파일 형식·크기를 client에서 사전 확인한다", () => {
    expect(validateRecordingDuration(4.9)).toContain("5초");
    expect(validateRecordingDuration(5)).toBeUndefined();
    expect(validateRecordingDuration(60)).toBeUndefined();
    expect(validateRecordingDuration(61)).toContain("60초");
    expect(validateEnrollmentFile(new File(["x"], "voice.mp3"))).toContain("WAV");
    expect(validateEnrollmentFile(new File(["x"], "voice.wav"))).toBeUndefined();
  });

  it("idempotency key를 action마다 생성한다", () => {
    expect(createIdempotencyKey()).not.toBe(createIdempotencyKey());
  });

  it("unknown API field와 내부 path를 DTO allowlist에서 제외한다", () => {
    const sample = mapVoiceSampleDto({
      id: "sample-1", source_type: "BROWSER_RECORDING", category: "BASIC_SPEECH",
      status: "READY", quality: { status: "WARNING", warnings: ["LOW_VOLUME"] },
      submit_eligible: true, storage_original_key: "private/path.wav",
    });
    const enrollment = mapVoiceEnrollmentDto({
      id: "enrollment-1", status: "READY_TO_SUBMIT", name: "내 목소리",
      consent_confirmed: true, samples: [sample], sample_count: 1, can_submit: true,
      validation_summary: { ready: 0, warning: 1, failed: 0 }, internal_path: "private",
    });
    expect(sample.quality.status).toBe("WARNING");
    expect(enrollment.samples).toHaveLength(1);
    expect(enrollment).not.toHaveProperty("internal_path");
    expect(enrollment.samples[0]).not.toHaveProperty("storage_original_key");
  });

  it("알 수 없는 status는 안전한 실패 상태로 mapping한다", () => {
    expect(mapVoiceEnrollmentDto({ status: "MADE_UP" }).status).toBe("FAILED");
    expect(mapVoiceSampleDto({ status: "MADE_UP", quality: {} }).status).toBe("FAILED");
  });

  it("품질과 normalization 오류를 사용자 문구로 mapping한다", () => {
    expect(qualityWarningMessage("LOW_VOLUME")).toContain("작게");
    const error = new ApiError(503, "VOICE_NORMALIZER_UNAVAILABLE", "internal");
    expect(voiceEnrollmentErrorMessage(error)).toContain("WAV 파일");
    expect(voiceEnrollmentErrorMessage(error)).not.toContain("internal");
  });

  it("만료와 not found에서만 session 복원 값을 제거하도록 분류한다", () => {
    expect(shouldClearEnrollmentSession(new ApiError(410, "VOICE_ENROLLMENT_EXPIRED", "expired"))).toBe(true);
    expect(shouldClearEnrollmentSession(new ApiError(0, "NETWORK_ERROR", "network"))).toBe(false);
  });

  it("sessionStorage에는 Enrollment ID와 단계 allowlist만 복원한다", () => {
    writeEnrollmentSession(sessionStorage, { enrollmentId: "enrollment-1", step: "quality" });
    expect(readEnrollmentSession(sessionStorage)).toEqual({ enrollmentId: "enrollment-1", step: "quality" });
    sessionStorage.setItem("doha.voice-enrollment.v1", JSON.stringify({ enrollmentId: "x", step: "made-up", blob: "secret" }));
    expect(readEnrollmentSession(sessionStorage)).toBeNull();
  });
});
