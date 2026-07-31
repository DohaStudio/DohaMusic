import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { MusicSettingsStep } from "@/features/studio/music-settings-step";
import { useStudioStore } from "@/stores/studio-store";

describe("K-POP Studio Preset", () => {
  beforeEach(() => useStudioStore.getState().reset());

  it("Dance를 기본 선택하고 Preset 선택을 Store에 반영한다", async () => {
    const user = userEvent.setup();
    render(<MusicSettingsStep />);
    expect(screen.getByRole("button", { name: /K-POP Dance/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(
      screen.getByRole("button", { name: /K-POP Easy Listening/ }),
    );

    expect(useStudioStore.getState().kpopPresetId).toBe(
      "kpop_easy_listening",
    );
  });
});
