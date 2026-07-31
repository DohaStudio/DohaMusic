import { describe, expect, it } from "vitest";
import { mapPipelineStatus, mapSafeFiles } from "@/lib/mappers";
describe("DTO mappers", () => {
  it("Pipeline 상태를 한국어 view로 매핑한다", () => {
    expect(mapPipelineStatus("VOICE_CONVERTING")).toMatchObject({
      label: "음색 변환",
      tone: "active",
    });
    expect(mapPipelineStatus("FAILED").tone).toBe("error");
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
});
