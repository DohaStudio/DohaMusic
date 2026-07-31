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
    });
  });
  it("초기 상태로 재설정한다", () => {
    useStudioStore.getState().patch({ voiceProfileId: "id" });
    useStudioStore.getState().reset();
    expect(useStudioStore.getState().voiceProfileId).toBe("");
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
    useStudioStore
      .getState()
      .patch({ prompt: "저장", apiKey: "secret" } as never);

    expect(sessionStorage.getItem("doha-studio-draft")).not.toContain("secret");
  });
});
