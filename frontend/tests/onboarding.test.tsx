import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Onboarding } from "@/components/onboarding";
import { useSettingsStore } from "@/stores/settings-store";

vi.mock("next/link", () => ({
  default: ({ href, children, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={String(href)} onClick={(event) => { event.preventDefault(); onClick?.(event); }} {...props}>{children}</a>
  ),
}));

describe("Onboarding", () => {
  beforeEach(async () => {
    localStorage.clear();
    useSettingsStore.setState({
      reducedMotion: null,
      onboardingCompleted: false,
      onboardingOpen: true,
    });
    await useSettingsStore.persist.rehydrate();
  });

  it("hydration 후 첫 방문 dialog를 표시하고 닫기를 완료 상태로 저장한다", async () => {
    const user = userEvent.setup();
    render(<Onboarding />);

    const dialog = await screen.findByRole("dialog", { name: "DohaMusic 시작하기" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-describedby", "onboarding-description");
    expect(screen.getByRole("button", { name: "닫기" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "닫기" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useSettingsStore.getState()).toMatchObject({
      onboardingCompleted: true,
      onboardingOpen: false,
    });
    expect(localStorage.getItem("doha-studio-settings")).toContain(
      '"onboardingCompleted":true',
    );
  });

  it("Escape로 닫고 Onboarding을 연 control로 focus를 복원한다", async () => {
    const user = userEvent.setup();
    const trigger = document.createElement("button");
    trigger.textContent = "시작 안내 다시 보기";
    document.body.append(trigger);
    trigger.focus();
    render(<Onboarding />);

    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("첫 음악 만들기는 완료 상태를 저장하고 /studio Link를 유지한다", async () => {
    const user = userEvent.setup();
    render(<Onboarding />);

    const link = await screen.findByRole("link", { name: "첫 음악 만들기" });
    expect(link).toHaveAttribute("href", "/studio");
    await user.click(link);

    expect(useSettingsStore.getState().onboardingCompleted).toBe(true);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("persisted 완료 상태를 hydration하면 remount 후에도 열리지 않는다", async () => {
    useSettingsStore.getState().completeOnboarding();
    const persisted = localStorage.getItem("doha-studio-settings") ?? "";
    useSettingsStore.setState({ onboardingCompleted: false, onboardingOpen: true });
    localStorage.setItem("doha-studio-settings", persisted);
    await useSettingsStore.persist.rehydrate();

    const first = render(<Onboarding />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    first.unmount();
    render(<Onboarding />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
