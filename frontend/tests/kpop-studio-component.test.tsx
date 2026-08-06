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

  it("고급 설정을 키보드로 열고 옵션을 수정·초기화한다", async () => {
    const user = userEvent.setup();
    render(<MusicSettingsStep />);
    await user.click(screen.getByText("K-POP 고급 설정"));
    const bpm = screen.getByLabelText("목표 BPM");
    await user.clear(bpm);
    await user.type(bpm, "130");
    expect(useStudioStore.getState().generationOptions.requestedBpm).toBe(130);
    expect(screen.getByRole("button", { name: "Post-Chorus" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "현재 스타일 기본값으로 초기화" }));
    expect(useStudioStore.getState().generationOptions.requestedBpm).toBe(124);
  });
});
