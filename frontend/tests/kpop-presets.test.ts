import { describe, expect, it } from "vitest";
import {
  compileKPopPrompt,
  DEFAULT_KPOP_PRESET_ID,
  getKPopPreset,
  KPOP_PRESETS,
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
});
