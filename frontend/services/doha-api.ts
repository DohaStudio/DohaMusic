import { apiRequest } from "./api-client";
import type {
  LyricsCreateDto,
  LyricsDocumentDto,
  LyricsValidationDto,
  PipelineCreateDto,
  PipelineFileDto,
  PipelineJobDto,
  VoiceProfileDto,
} from "@/types/api";

export const dohaApi = {
  health: () => apiRequest<{ status: string }>("/health"),
  createLyrics: (data: LyricsCreateDto) =>
    apiRequest<LyricsDocumentDto>("/api/lyrics", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getLyrics: (id: string) => apiRequest<LyricsDocumentDto>(`/api/lyrics/${id}`),
  reviseLyrics: (id: string, instruction: string) =>
    apiRequest<LyricsDocumentDto>(`/api/lyrics/${id}/revise`, {
      method: "POST",
      body: JSON.stringify({ instruction, preserve_structure: true }),
    }),
  validateLyrics: (raw_lyrics: string) =>
    apiRequest<LyricsValidationDto>("/api/lyrics/validate", {
      method: "POST",
      body: JSON.stringify({ raw_lyrics, language: "ko" }),
    }),
  deleteLyrics: (id: string) =>
    apiRequest<void>(`/api/lyrics/${id}`, { method: "DELETE" }),
  createVoiceProfile: (data: {
    name: string;
    reference_file_path: string;
    consent_confirmed: true;
  }) =>
    apiRequest<VoiceProfileDto>("/api/voice-profiles", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteVoiceProfile: (id: string) =>
    apiRequest<void>(`/api/voice-profiles/${id}`, { method: "DELETE" }),
  createPipeline: (data: PipelineCreateDto) =>
    apiRequest<PipelineJobDto>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getPipeline: (id: string, signal?: AbortSignal) =>
    apiRequest<PipelineJobDto>(`/api/pipelines/${id}`, { signal }),
  getPipelineFiles: (id: string) =>
    apiRequest<PipelineFileDto[]>(`/api/pipelines/${id}/files`),
};

export function getPipelineFileContentUrl(jobId: string, fileId: string) {
  return `/backend/api/pipelines/${encodeURIComponent(jobId)}/files/${encodeURIComponent(fileId)}/content`;
}

export function getPipelineFileDownloadUrl(jobId: string, fileId: string) {
  return `/backend/api/pipelines/${encodeURIComponent(jobId)}/files/${encodeURIComponent(fileId)}/download`;
}

export function toBackendPublicUrl(url: string | null): string | undefined {
  return url?.startsWith("/api/") ? `/backend${url}` : undefined;
}
