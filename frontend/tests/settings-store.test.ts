import { beforeEach, describe, expect, it } from "vitest";
import { useSettingsStore } from "@/stores/settings-store";

describe("Settings store", () => {
  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.getState().reset();
  });

  it("reduced motion을 localStorage에 저장하고 reset한다", () => {
    useSettingsStore.getState().setReducedMotion(true);

    expect(useSettingsStore.getState().reducedMotion).toBe(true);
    expect(localStorage.getItem("doha-studio-settings")).toContain(
      '"reducedMotion":true',
    );

    useSettingsStore.getState().reset();
    expect(useSettingsStore.getState().reducedMotion).toBeNull();
  });

  it("localStorage 상태를 다시 hydration한다", async () => {
    localStorage.setItem(
      "doha-studio-settings",
      JSON.stringify({ state: { reducedMotion: false }, version: 0 }),
    );

    await useSettingsStore.persist.rehydrate();

    expect(useSettingsStore.getState().reducedMotion).toBe(false);
  });

  it("Onboarding 완료·다시 보기·reset 상태를 일관되게 관리한다", () => {
    useSettingsStore.getState().completeOnboarding();
    expect(useSettingsStore.getState()).toMatchObject({ onboardingCompleted: true, onboardingOpen: false });

    useSettingsStore.getState().reopenOnboarding();
    expect(useSettingsStore.getState()).toMatchObject({ onboardingCompleted: false, onboardingOpen: true });

    useSettingsStore.getState().completeOnboarding();
    useSettingsStore.getState().reset();
    expect(useSettingsStore.getState()).toMatchObject({ onboardingCompleted: false, onboardingOpen: true });
  });

  it("persist에는 완료 authority만 저장하고 hydration 시 transient open을 덮어쓰지 않는다", async () => {
    useSettingsStore.getState().completeOnboarding();
    const persisted = localStorage.getItem("doha-studio-settings") ?? "";
    expect(persisted).toContain('"onboardingCompleted":true');
    expect(persisted).not.toContain("onboardingOpen");

    useSettingsStore.setState({ onboardingCompleted: false, onboardingOpen: true });
    localStorage.setItem("doha-studio-settings", persisted);
    await useSettingsStore.persist.rehydrate();
    expect(useSettingsStore.getState()).toMatchObject({ onboardingCompleted: true, onboardingOpen: true });
  });
});
