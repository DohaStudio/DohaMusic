import { apiRequest } from "./api-client";
import type {
  LyricsCreateDto,
  LyricsDocumentDto,
  LyricsValidationDto,
  PipelineCreateDto,
  PipelineFileDto,
  PipelineJobDto,
  VoiceProfileDto,
  HistoryDetailDto,
  HistoryItemDto,
  ProjectDetailDto,
  ProjectDto,
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
  uploadVoiceProfile: (data: {
    file: File;
    name: string;
    consentTextVersion: string;
  }) => {
    const body = new FormData();
    body.set("file", data.file);
    body.set("name", data.name);
    body.set("consent_confirmed", "true");
    body.set("consent_text_version", data.consentTextVersion);
    return apiRequest<VoiceProfileDto>(
      "/api/voice-profiles/upload",
      { method: "POST", body },
      60_000,
    );
  },
  listVoiceProfiles: () =>
    apiRequest<VoiceProfileDto[]>("/api/voice-profiles"),
  getVoiceProfile: (id: string) =>
    apiRequest<VoiceProfileDto>(
      `/api/voice-profiles/${encodeURIComponent(id)}`,
    ),
  deleteVoiceProfile: (id: string) =>
    apiRequest<void>(`/api/voice-profiles/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  createPipeline: (data: PipelineCreateDto) =>
    apiRequest<PipelineJobDto>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getPipeline: (id: string, signal?: AbortSignal) =>
    apiRequest<PipelineJobDto>(`/api/pipelines/${id}`, { signal }),
  getPipelineFiles: (id: string) =>
    apiRequest<PipelineFileDto[]>(`/api/pipelines/${id}/files`),
  getHistory: (options: { limit?: number; offset?: number; status?: string; q?: string } = {}) => {
    const params = new URLSearchParams();
    if (options.limit) params.set("limit", String(options.limit));
    if (options.offset) params.set("offset", String(options.offset));
    if (options.status) params.set("status", options.status);
    if (options.q) params.set("q", options.q);
    const suffix = params.size ? `?${params}` : "";
    return apiRequest<HistoryItemDto[]>(`/api/history${suffix}`);
  },
  getHistoryDetail: (id: string) =>
    apiRequest<HistoryDetailDto>(`/api/history/${encodeURIComponent(id)}`),
  getProjects: () => apiRequest<ProjectDto[]>("/api/projects"),
  getProject: (id: string) =>
    apiRequest<ProjectDetailDto>(`/api/projects/${encodeURIComponent(id)}`),
  createProject: (data: { title: string; description?: string }) =>
    apiRequest<ProjectDto>("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProject: (id: string, data: { title?: string; description?: string | null }) =>
    apiRequest<ProjectDto>(`/api/projects/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteProject: (id: string) =>
    apiRequest<void>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),
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
