import type {
  LyricsDocumentDto,
  PipelineStatus,
} from "@/types/api";
import type {
  LyricsView,
  PipelineStageView,
  SafePipelineFile,
} from "@/types/domain";

const pipelineLabels: Readonly<Record<PipelineStatus, string>> = {
  PENDING: "곧 시작합니다",
  VALIDATING: "요청을 확인하고 있습니다",
  GENERATING: "음악 초안을 만들고 있습니다",
  STEM_SEPARATING: "보컬과 반주를 나누고 있습니다",
  VOICE_CONVERTING: "내 목소리를 적용하고 있습니다",
  MIXING: "목소리와 반주를 다듬고 있습니다",
  EXPORTING: "완성 파일을 준비하고 있습니다",
  CANCEL_REQUESTED: "취소 요청을 처리하고 있습니다",
  COMPLETED: "음악이 완성되었습니다",
  FAILED: "음악을 완성하지 못했습니다",
  CANCELLED: "음악 만들기가 취소되었습니다",
};

const preferredFileTypes = [
  "final",
  "music",
  "converted_voice",
  "vocals",
  "instrumental",
] as const;

export function mapPipelineStatus(status: PipelineStatus): PipelineStageView {
  const tone: PipelineStageView["tone"] =
    status === "COMPLETED"
      ? "success"
      : status === "FAILED"
        ? "error"
        : status === "PENDING" || status === "CANCELLED"
          ? "neutral"
          : "active";
  return { status, label: pipelineLabels[status], tone };
}

export function mapSafeFiles(files: readonly unknown[]): SafePipelineFile[] {
  return files.flatMap((value) => {
    if (!isRecord(value)) return [];
    const id = readString(value, "id");
    const jobId = readString(value, "job_id");
    const fileType = readString(value, "file_type");
    const mimeType = readString(value, "mime_type");
    const createdAt = readDateString(value, "created_at");
    if (!id || !jobId || !fileType || !mimeType || !createdAt) return [];

    const contentUrl = publicBackendUrl(value.content_url);
    const downloadUrl = publicBackendUrl(value.download_url);
    const contentAvailable = value.content_available === true && Boolean(contentUrl);
    const downloadAvailable =
      value.download_available === true && Boolean(downloadUrl);

    return [
      {
        id,
        jobId,
        fileType,
        mimeType,
        createdAt,
        contentAvailable,
        downloadAvailable,
        ...(contentAvailable ? { contentUrl } : {}),
        ...(downloadAvailable ? { downloadUrl } : {}),
      },
    ];
  });
}

export function selectPreferredAudioFile(
  files: readonly SafePipelineFile[],
): SafePipelineFile | undefined {
  const playable = files.filter(
    (file) => file.contentAvailable && Boolean(file.contentUrl),
  );
  for (const fileType of preferredFileTypes) {
    const match = playable.find((file) => file.fileType === fileType);
    if (match) return match;
  }
  return playable[0];
}

export function mapLyrics(document: LyricsDocumentDto): LyricsView {
  return {
    id: document.id,
    title: document.title?.trim() || document.topic.trim() || "제목 없는 가사",
    fullText: document.full_text,
    sections: document.sections,
    providerLabel: document.provider,
    modelLabel: [document.model_name, document.model_version]
      .filter(Boolean)
      .join(" "),
    version: document.version,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(
  value: Record<string, unknown>,
  key: string,
): string | undefined {
  const candidate = value[key];
  return typeof candidate === "string" && candidate.trim()
    ? candidate
    : undefined;
}

function readDateString(
  value: Record<string, unknown>,
  key: string,
): string | undefined {
  const candidate = readString(value, key);
  return candidate && Number.isFinite(Date.parse(candidate))
    ? candidate
    : undefined;
}

function publicBackendUrl(value: unknown): string | undefined {
  return typeof value === "string" && value.startsWith("/api/")
    ? `/backend${value}`
    : undefined;
}
