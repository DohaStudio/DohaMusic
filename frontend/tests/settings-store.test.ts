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
});
