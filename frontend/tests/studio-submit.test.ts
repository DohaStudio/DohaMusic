import { describe, expect, it } from "vitest";
import { toPipelineCreate } from "@/features/studio/studio-submit";

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
    });

    expect(request.genre).toBe("kpop_easy_listening");
    expect(request.prompt).toContain("Additional genre direction: 신스 팝");
    expect(request.prompt).toContain("User request (highest priority");
    expect(request.prompt).toMatch(/따뜻한 여름 저녁을 걷는 곡$/);
    expect(Object.keys(request).sort()).toEqual(
      [
        "duration_seconds",
        "genre",
        "lyrics",
        "prompt",
        "seed",
        "voice_profile_id",
      ].sort(),
    );
    expect(request).not.toHaveProperty("preset_id");
    expect(request).not.toHaveProperty("generation_options");
  });
});
