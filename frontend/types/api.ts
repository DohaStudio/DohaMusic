export type PipelineStatus =
  | "PENDING"
  | "VALIDATING"
  | "GENERATING"
  | "STEM_SEPARATING"
  | "VOICE_CONVERTING"
  | "MIXING"
  | "EXPORTING"
  | "COMPLETED"
  | "FAILED";

export interface LyricsSectionDto {
  section_type: string;
  lines: string[];
}
export interface LyricsValidationDto {
  valid: boolean;
  normalized_lyrics: string;
  sections: LyricsSectionDto[];
  warnings: string[];
  errors: string[];
  character_count: number;
  line_count: number;
  section_count: number;
  repetition_ratio: number;
}
export interface LyricsDocumentDto {
  id: string;
  parent_id: string | null;
  version: number;
  revision_instruction: string | null;
  source_hash: string | null;
  result_hash: string | null;
  title: string | null;
  language: string;
  topic: string;
  genre: string | null;
  mood: string | null;
  keywords: string[];
  structure: string[];
  sections: LyricsSectionDto[];
  full_text: string;
  provider: string;
  model_name: string;
  model_version: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
export interface LyricsCreateDto {
  topic: string;
  genre?: string;
  mood?: string;
  language: string;
  keywords: string[];
  structure: string[];
  target_duration_seconds?: number;
  additional_instructions?: string;
  allow_template_fallback: boolean;
}
export interface VoiceProfileDto {
  id: string;
  name: string;
  consent_confirmed: boolean;
  created_at: string;
  updated_at: string;
}
export interface PipelineCreateDto {
  prompt: string;
  lyrics?: string;
  genre?: string;
  duration_seconds: number;
  seed?: number;
  voice_profile_id: string;
}
export interface PipelineJobDto {
  id: string;
  voice_profile_id: string;
  status: PipelineStatus;
  current_step: string;
  progress_percent: number;
  prompt: string;
  lyrics: string | null;
  genre: string | null;
  duration_seconds: number;
  seed: number | null;
  pipeline_version: string;
  result_metadata: Record<string, unknown>;
  failed_step: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}
export interface PipelineFileDto {
  id: string;
  job_id: string;
  file_type: string;
  mime_type: string;
  created_at: string;
  content_available: boolean;
  download_available: boolean;
  content_url: string | null;
  download_url: string | null;
}
