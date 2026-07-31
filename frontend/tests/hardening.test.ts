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
  it("null과 알 수 없는 metadata에는 빈 목록을 반환한다", () => {
    expect(publicMetadataRows(null)).toEqual([]);
    expect(publicMetadataRows({ file_path: "secret", unknown: 1 })).toEqual([]);
  });
  it("K-POP 공개 설정만 Result metadata에 표시한다", () => {
    const rows = publicMetadataRows({
      generation_options: {
        preset_id: "kpop_dance",
        requested_bpm: 124,
        language_ratio: { ko: 70, en: 30 },
        hook: { phrase: "Play My Heart" },
        vocal_energy: "medium",
        concept: "confident_bright",
        provider_secret: "hidden",
      },
      kpop_prompt_compiler_version: "kpop-prompt-v1",
      compiled_prompt: "internal",
    });
    expect(rows).toEqual(expect.arrayContaining([
      { label: "K-POP 스타일", value: "K-POP Dance" },
      { label: "목표 BPM", value: "124 BPM (Prompt 목표)" },
      { label: "후렴 Hook", value: "Play My Heart" },
      { label: "K-POP Compiler", value: "kpop-prompt-v1" },
    ]));
    expect(JSON.stringify(rows)).not.toContain("hidden");
    expect(JSON.stringify(rows)).not.toContain("internal");
  });
  it("Mixer 공개 품질값만 노출하고 내부 필드는 제외한다", () => {
    const rows = publicMetadataRows({
      step_execution: [
        {
          step: "mixer",
          status: "COMPLETED",
          audio_quality: {
            sample_rate: 48000,
            channels: 2,
            peak_dbfs: -1.2,
            model_path: "C:/private/model",
            clipping: { detected: false, internal_buffer: "secret" },
          },
        },
      ],
    });
    const value = JSON.stringify(rows);
    expect(value).toContain("48000");
    expect(value).toContain("Clipping");
    expect(value).not.toContain("private");
    expect(value).not.toContain("internal_buffer");
  });
});
