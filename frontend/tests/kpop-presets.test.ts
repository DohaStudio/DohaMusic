import { describe, expect, it } from "vitest";
import {
  compileKPopPrompt,
  DEFAULT_KPOP_PRESET_ID,
  getKPopPreset,
  KPOP_PRESETS,
  KPOP_GENERATION_CAPABILITIES,
  createDefaultKPopGenerationOptions,
  validateKPopGenerationOptions,
} from "@/features/studio/kpop-presets";

describe("K-POP Preset과 Prompt Compiler", () => {
  it("Provider와 무관한 3개 Preset과 Dance 기본값을 제공한다", () => {
    expect(DEFAULT_KPOP_PRESET_ID).toBe("kpop_dance");
    expect(KPOP_PRESETS.map((preset) => preset.id)).toEqual([
      "kpop_dance",
      "kpop_easy_listening",
      "kpop_performance",
    ]);
    expect(getKPopPreset("kpop_dance").defaultPrompt.toLowerCase()).not.toContain(
      "ace-step",
    );
    expect(KPOP_GENERATION_CAPABILITIES.requestedBpm).toBe("prompt_compiled");
    expect(KPOP_GENERATION_CAPABILITIES.detectedBpm).toBe("not_supported");
  });

  it("사용자 Prompt를 Custom과 Preset보다 높은 우선순위로 컴파일한다", () => {
    const result = compileKPopPrompt({
      presetId: "kpop_dance",
      userPrompt: "여름 느낌의 자신감 있는 곡",
      customPrompt: "Mood: refreshing",
    });
    expect(result.prompt.indexOf("Preset direction")).toBeLessThan(
      result.prompt.indexOf("Additional user direction"),
    );
    expect(result.prompt.indexOf("Additional user direction")).toBeLessThan(
      result.prompt.indexOf("User request (highest priority"),
    );
    expect(result.prompt).toMatch(/여름 느낌의 자신감 있는 곡$/);
    expect(result.genre).toBe("kpop_dance");
    expect(result.compilerVersion).toBe("kpop-prompt-v1");
  });

  it("특정 아티스트 모방 요청을 거부한다", () => {
    expect(() =>
      compileKPopPrompt({
        presetId: "kpop_performance",
        userPrompt: "유명 가수처럼 노래해 줘",
      }),
    ).toThrow(/모방은 지원하지 않습니다/);
  });

  it("Preset별 구조화 기본값을 제공한다", () => {
    expect(createDefaultKPopGenerationOptions("kpop_dance")).toMatchObject({ requestedBpm: 124, languageRatio: { ko: 70, en: 30 }, includeDanceBreak: false, vocalEnergy: "medium" });
    expect(createDefaultKPopGenerationOptions("kpop_easy_listening")).toMatchObject({ requestedBpm: 104, languageRatio: { ko: 80, en: 20 }, vocalEnergy: "low" });
    expect(createDefaultKPopGenerationOptions("kpop_performance")).toMatchObject({ requestedBpm: 142, languageRatio: { ko: 60, en: 40 }, includeDanceBreak: true, vocalEnergy: "high" });
  });

  it("구조화 옵션을 Preview에 deterministic하게 반영한다", () => {
    const options = { ...createDefaultKPopGenerationOptions("kpop_dance"), hook: { phrase: "Play My Heart", style: "chant" as const, repeatCount: 3 } };
    const first = compileKPopPrompt({ presetId: "kpop_dance", userPrompt: "여름밤", options });
    const second = compileKPopPrompt({ presetId: "kpop_dance", userPrompt: "여름밤", options });
    expect(first.prompt).toBe(second.prompt);
    expect(first.prompt).toContain("124 BPM");
    expect(first.prompt).toContain("70% Korean and 30% English");
    expect(first.prompt).toContain('"Play My Heart"');
    expect(first.prompt).toMatch(/여름밤$/);
  });

  it("BPM·언어 비율·Hook 검증 오류를 거부한다", () => {
    const base = createDefaultKPopGenerationOptions("kpop_dance");
    expect(() => validateKPopGenerationOptions({ ...base, requestedBpm: 181 })).toThrow(/70에서 180/);
    expect(() => validateKPopGenerationOptions({ ...base, languageRatio: { ko: 70, en: 20 } })).toThrow(/합은 100/);
    expect(() => validateKPopGenerationOptions({ ...base, hook: { phrase: "", style: "chant", repeatCount: 2 } })).toThrow(/1~40자/);
  });
});
