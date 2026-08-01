import { apiRequest } from "./api-client";
import type {
  LyricsCreateDto,
  LyricsDocumentDto,
  LyricsValidationDto,
  PipelineCreateDto,
  PipelineFileDto,
  PipelineJobDto,
  PipelineCancelDto,
  PipelineRetryDto,
  VoiceProfileDto,
  HistoryDetailDto,
  HistoryItemDto,
  ProjectDetailDto,
  ProjectDto,
} from "@/types/api";
import type {
  VoiceEnrollmentCreateRequest,
  VoiceEnrollmentSubmitRequest,
  VoiceSampleSourceType,
} from "@/features/voice/voice-enrollment-types";
import {
  mapVoiceEnrollmentDto,
  mapVoiceSampleDto,
} from "@/features/voice/voice-enrollment-utils";

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
  createVoiceEnrollment: (data: VoiceEnrollmentCreateRequest, idempotencyKey: string) =>
    apiRequest<unknown>("/api/voice-enrollments", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(data),
    }).then(mapVoiceEnrollmentDto),
  getVoiceEnrollment: (id: string, signal?: AbortSignal) =>
    apiRequest<unknown>(`/api/voice-enrollments/${encodeURIComponent(id)}`, { signal })
      .then(mapVoiceEnrollmentDto),
  uploadVoiceEnrollmentSample: (data: {
    enrollmentId: string;
    file: File | Blob;
    sourceType: VoiceSampleSourceType;
    category: string;
    promptId?: string;
    idempotencyKey: string;
    signal?: AbortSignal;
  }) => {
    const body = new FormData();
    body.set("file", data.file, data.file instanceof File ? data.file.name : `recording.${data.file.type.includes("ogg") ? "ogg" : data.file.type.includes("wav") ? "wav" : "webm"}`);
    body.set("source_type", data.sourceType);
    body.set("category", data.category);
    if (data.promptId) body.set("prompt_id", data.promptId);
    return apiRequest<unknown>(
      `/api/voice-enrollments/${encodeURIComponent(data.enrollmentId)}/samples`,
      {
        method: "POST",
        headers: { "Idempotency-Key": data.idempotencyKey },
        body,
        signal: data.signal,
      },
      90_000,
    ).then(mapVoiceSampleDto);
  },
  getVoiceEnrollmentSample: (enrollmentId: string, sampleId: string, signal?: AbortSignal) =>
    apiRequest<unknown>(
      `/api/voice-enrollments/${encodeURIComponent(enrollmentId)}/samples/${encodeURIComponent(sampleId)}`,
      { signal },
    ).then(mapVoiceSampleDto),
  deleteVoiceEnrollmentSample: (enrollmentId: string, sampleId: string) =>
    apiRequest<unknown>(
      `/api/voice-enrollments/${encodeURIComponent(enrollmentId)}/samples/${encodeURIComponent(sampleId)}`,
      { method: "DELETE" },
    ).then(mapVoiceSampleDto),
  submitVoiceEnrollment: (
    enrollmentId: string,
    data: VoiceEnrollmentSubmitRequest,
    idempotencyKey: string,
  ) => apiRequest<unknown>(
    `/api/voice-enrollments/${encodeURIComponent(enrollmentId)}/submit`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(data),
    },
    90_000,
  ).then(mapVoiceEnrollmentDto),
  cancelVoiceEnrollment: (enrollmentId: string) =>
    apiRequest<unknown>(
      `/api/voice-enrollments/${encodeURIComponent(enrollmentId)}/cancel`,
      { method: "POST" },
      30_000,
    ).then(mapVoiceEnrollmentDto),
  createPipeline: (data: PipelineCreateDto) =>
    apiRequest<PipelineJobDto>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getPipeline: (id: string, signal?: AbortSignal) =>
    apiRequest<PipelineJobDto>(`/api/pipelines/${id}`, { signal }),
  cancelPipelineJob: (id: string, signal?: AbortSignal) =>
    apiRequest<PipelineCancelDto>(`/api/pipelines/${encodeURIComponent(id)}/cancel`, { method: "POST", signal }),
  retryPipelineJob: (id: string, signal?: AbortSignal) =>
    apiRequest<PipelineRetryDto>(`/api/pipelines/${encodeURIComponent(id)}/retry`, { method: "POST", signal }),
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
