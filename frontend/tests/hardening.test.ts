import { describe, expect, it } from "vitest";
import { isRevisionSupported } from "@/features/lyrics/lyrics-lab";
import { publicMetadataRows } from "@/lib/result-metadata";
import type { LyricsDocumentDto } from "@/types/api";
const lyrics = (revision: boolean): LyricsDocumentDto => ({
  id: "l",
  parent_id: null,
  version: 1,
  revision_instruction: null,
  source_hash: null,
  result_hash: null,
  title: null,
  language: "ko",
  topic: "t",
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
  metadata: { capabilities: { revision } },
  created_at: "",
  updated_at: "",
});
describe("hardening helpers", () => {
  it("Backend capability로 revision을 제어한다", () => {
    expect(isRevisionSupported(lyrics(false))).toBe(false);
    expect(isRevisionSupported(lyrics(true))).toBe(true);
  });
  it("Result metadata allowlist만 노출한다", () => {
    const rows = publicMetadataRows({
      duration_seconds: 30,
      execution_time_seconds: 2,
      file_path: "secret",
      command: "rm",
      providers: { music: { provider: "mock", model_path: "secret" } },
      nested: { api_key: "secret" },
    });
    const value = JSON.stringify(rows);
    expect(value).toContain("mock");
    expect(value).not.toContain("secret");
    expect(value).not.toContain("command");
  });
});
