import { describe, expect, it } from "vitest";
import { toPipelineCreate } from "@/features/studio/studio-submit";
import { createDefaultKPopGenerationOptions } from "@/features/studio/kpop-presets";

describe("K-POP Studio Pipeline 요청", () => {
  it("Preset을 컴파일하고 기존 Pipeline DTO 필드만 전송한다", () => {
    const request = toPipelineCreate({
      kpopPresetId: "kpop_easy_listening",
      prompt: "따뜻한 여름 저녁을 걷는 곡",
      genre: "신스 팝",
      selectedMoods: ["감성적인"],
      lyricsText: "[Verse]\n따뜻한 바람",
      durationSeconds: 30,
      seed: 7,
      voiceProfileId: "voice-id",
      generationOptions: {
        ...createDefaultKPopGenerationOptions("kpop_easy_listening"),
        hook: { phrase: "따뜻한 바람", style: "title_repeat", repeatCount: 2 },
      },
    });

    expect(request.genre).toBe("kpop_easy_listening");
    expect(request.prompt).toBe("따뜻한 여름 저녁을 걷는 곡");
    expect(Object.keys(request).sort()).toEqual(
      [
        "duration_seconds",
        "genre",
        "lyrics",
        "prompt",
        "seed",
        "voice_profile_id",
        "generation_options",
      ].sort(),
    );
    expect(request).not.toHaveProperty("preset_id");
    expect(request.generation_options).toEqual(expect.objectContaining({
      preset_id: "kpop_easy_listening",
      requested_bpm: 104,
      language_ratio: { ko: 80, en: 20 },
      hook: { phrase: "따뜻한 바람", style: "title_repeat", repeat_count: 2 },
      vocal_energy: "low",
      concept: "warm_fresh, 신스 팝, 감성적인",
    }));
  });
});
