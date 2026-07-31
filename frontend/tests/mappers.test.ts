import { describe, expect, it } from "vitest";
import {
  mapLyrics,
  mapPipelineStatus,
  mapSafeFiles,
} from "@/lib/mappers";
import type { LyricsDocumentDto } from "@/types/api";
describe("DTO mappers", () => {
  it("Pipeline 상태를 한국어 view로 매핑한다", () => {
    expect(mapPipelineStatus("VOICE_CONVERTING")).toMatchObject({
      label: "내 목소리를 적용하고 있습니다",
      tone: "active",
    });
    expect(mapPipelineStatus("FAILED").tone).toBe("error");
    expect(mapPipelineStatus("PENDING").label).toBe("곧 시작합니다");
  });
  it("public file DTO에 내부 경로가 없다", () => {
    const result = mapSafeFiles([
      {
        id: "f",
        job_id: "j",
        file_type: "final",
        mime_type: "audio/wav",
        created_at: "2026-07-31T00:00:00Z",
        content_available: false,
        download_available: false,
        content_url: null,
        download_url: null,
      },
    ]);
    expect(result[0]).not.toHaveProperty("filePath");
    expect(JSON.stringify(result)).not.toContain("path");
  });
  it("필수 필드가 없거나 URL이 외부인 file DTO를 안전하게 거부한다", () => {
    const result = mapSafeFiles([
      null,
      { id: "missing-fields" },
      {
        id: "unsafe",
        job_id: "job",
        file_type: "final",
        mime_type: "audio/wav",
        created_at: "not-a-date",
        content_available: true,
        content_url: "https://example.com/private.wav",
      },
    ]);
    expect(result).toEqual([]);
  });
  it("공개 API URL만 same-origin Backend URL로 변환한다", () => {
    const [file] = mapSafeFiles([
      {
        id: "file",
        job_id: "job/id",
        file_type: "final",
        mime_type: "audio/wav",
        created_at: "2026-07-31T00:00:00Z",
        content_available: true,
        download_available: true,
        content_url: "/api/pipelines/job/files/file/content",
        download_url: "/api/pipelines/job/files/file/download",
      },
    ]);
    expect(file).toMatchObject({
      contentAvailable: true,
      downloadAvailable: true,
      contentUrl: "/backend/api/pipelines/job/files/file/content",
      downloadUrl: "/backend/api/pipelines/job/files/file/download",
    });
  });
  it("가사 제목과 모델 표시값에 안전한 fallback을 사용한다", () => {
    const document: LyricsDocumentDto = {
      id: "lyrics",
      parent_id: null,
      version: 1,
      revision_instruction: null,
      source_hash: null,
      result_hash: null,
      title: null,
      language: "ko",
      topic: "여름밤",
      genre: null,
      mood: null,
      keywords: [],
      structure: [],
      sections: [],
      full_text: "text",
      provider: "template",
      model_name: "template",
      model_version: null,
      status: "GENERATED",
      metadata: {},
      created_at: "2026-07-31T00:00:00Z",
      updated_at: "2026-07-31T00:00:00Z",
    };
    expect(mapLyrics(document)).toMatchObject({
      title: "여름밤",
      providerLabel: "template",
      modelLabel: "template",
    });
  });
});
