import { beforeEach, describe, expect, it } from "vitest";
import { useStudioStore } from "@/stores/studio-store";
describe("Studio store", () => {
  beforeEach(() => useStudioStore.getState().reset());
  it("draft와 단계를 갱신한다", () => {
    useStudioStore.getState().patch({ prompt: "새벽 R&B" });
    useStudioStore.getState().setStep("lyrics");
    expect(useStudioStore.getState()).toMatchObject({
      prompt: "새벽 R&B",
      currentStep: "lyrics",
      kpopPresetId: "kpop_dance",
    });
  });
  it("초기 상태로 재설정한다", () => {
    useStudioStore.getState().patch({ voiceProfileId: "id" });
    useStudioStore.getState().reset();
    expect(useStudioStore.getState().voiceProfileId).toBe("");
  });

  it("수정 전에는 Preset 기본값을 적용하고 수정 후에는 Custom 값을 보존한다", () => {
    useStudioStore.getState().selectKPopPreset("kpop_performance");
    expect(useStudioStore.getState().generationOptions).toMatchObject({ requestedBpm: 142, includeDanceBreak: true });
    useStudioStore.getState().updateGenerationOptions({ requestedBpm: 150 });
    useStudioStore.getState().selectKPopPreset("kpop_easy_listening");
    expect(useStudioStore.getState().generationOptions).toMatchObject({ presetId: "kpop_easy_listening", requestedBpm: 150 });
    useStudioStore.getState().resetGenerationOptions();
    expect(useStudioStore.getState().generationOptions.requestedBpm).toBe(104);
  });

  it("session draft를 hydration하고 allowlist 밖 민감 값은 저장하지 않는다", async () => {
    sessionStorage.setItem(
      "doha-studio-draft",
      JSON.stringify({
        state: { prompt: "복원된 초안", currentStep: "lyrics" },
        version: 0,
      }),
    );
    await useStudioStore.persist.rehydrate();

    expect(useStudioStore.getState().prompt).toBe("복원된 초안");
    expect(useStudioStore.getState().generationOptions).toMatchObject({ presetId: "kpop_dance", requestedBpm: 124 });
    useStudioStore
      .getState()
      .patch({ prompt: "저장", apiKey: "secret" } as never);

    expect(sessionStorage.getItem("doha-studio-draft")).not.toContain("secret");
  });
});
