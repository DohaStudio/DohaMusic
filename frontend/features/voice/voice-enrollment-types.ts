export const VOICE_CONSENT_POLICY_VERSION = "v1";
export const VOICE_ENROLLMENT_SESSION_KEY = "doha.voice-enrollment.v1";
export const MAX_VOICE_SAMPLES = 10;
export const MIN_VOICE_DURATION_SECONDS = 5;
export const MAX_VOICE_DURATION_SECONDS = 60;
export const MAX_VOICE_SAMPLE_BYTES = 25 * 1024 * 1024;

export type VoiceEnrollmentStatus =
  | "DRAFT"
  | "READY_TO_SUBMIT"
  | "SUBMITTING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED"
  | "DELETE_PENDING"
  | "DELETE_FAILED";

export type VoiceSampleStatus =
  | "UPLOADED"
  | "VALIDATING"
  | "READY"
  | "FAILED"
  | "PROMOTED"
  | "DELETE_PENDING"
  | "DELETE_FAILED"
  | "DELETED";

export type VoiceQualityStatus = "PASS" | "WARNING" | "FAIL";
export type VoiceSampleSourceType = "BROWSER_RECORDING" | "FILE_UPLOAD";

export interface VoiceQualityResultDto {
  status: VoiceQualityStatus;
  warnings: string[];
  version: string | null;
  peak: number | null;
  rms: number | null;
  silence_ratio: number | null;
  clipping_ratio: number | null;
}

export interface VoiceEnrollmentSampleDto {
  id: string;
  enrollment_id: string | null;
  source_type: VoiceSampleSourceType;
  prompt_id: string | null;
  category: string;
  status: VoiceSampleStatus;
  original_content_type: string | null;
  original_size_bytes: number | null;
  normalized_content_type: string | null;
  normalized_size_bytes: number | null;
  duration_seconds: number | null;
  sample_rate: number | null;
  channels: number | null;
  bit_depth: number | null;
  quality: VoiceQualityResultDto;
  failure_code: string | null;
  submit_eligible: boolean;
  cleanup_status: string;
  created_at: string;
  validated_at: string | null;
}

export interface VoiceEnrollmentDto {
  id: string;
  status: VoiceEnrollmentStatus;
  name: string;
  description: string | null;
  consent_confirmed: boolean;
  consent_policy_version: string | null;
  sample_count: number;
  samples: VoiceEnrollmentSampleDto[];
  can_submit: boolean;
  validation_summary: { ready: number; warning: number; failed: number };
  cleanup_status: string;
  cleanup_failure_code: string | null;
  voice_profile_id: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  absolute_expires_at: string | null;
}

export interface VoiceEnrollmentCreateRequest {
  name: string;
  description: string | null;
  consent_confirmed: true;
  consent_policy_version: string;
}

export interface VoiceEnrollmentSubmitRequest {
  active_reference_sample_id: string;
  included_sample_ids: string[];
  acknowledged_warning_codes: Array<{ sample_id: string; codes: string[] }>;
  consent_confirmed: true;
  consent_policy_version: string;
}

export type VoiceEnrollmentStep =
  | "guide"
  | "consent"
  | "method"
  | "samples"
  | "quality"
  | "reference"
  | "review"
  | "complete";

export interface VoiceEnrollmentSession {
  enrollmentId: string;
  step: VoiceEnrollmentStep;
}
