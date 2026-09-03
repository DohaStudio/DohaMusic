import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { StudioWorkspace } from "@/features/studio/studio-workspace";
import { useStudioStore } from "@/stores/studio-store";

let pathname = "/studio";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={String(href)} {...props}>{children}</a>
  ),
}));
vi.mock("@/components/api-status", () => ({ ApiStatus: () => <span>API</span> }));
vi.mock("@/features/player/global-player", () => ({ GlobalPlayer: () => null }));
vi.mock("@/components/brand", () => ({ Brand: ({ compact }: { compact?: boolean }) => <span>{compact ? "D" : "DohaMusic"}</span> }));

function renderShell(children: ReactNode = <div>Content</div>) {
  return render(<AppShell>{children}</AppShell>);
}

describe("Studio와 DAW navigation", () => {
  beforeEach(() => {
    pathname = "/studio";
    useStudioStore.getState().reset();
  });

  it("Desktop과 Mobile에서 프로젝트 · DAW를 제공하고 nested Project를 active로 표시한다", () => {
    pathname = "/projects/project-1";
    renderShell();

    const desktop = screen.getByRole("navigation", { name: "주요 메뉴" });
    const mobile = screen.getByRole("navigation", { name: "모바일 메뉴" });
    expect(within(desktop).getByRole("link", { name: "프로젝트 · DAW" })).toHaveAttribute("aria-current", "page");
    expect(within(mobile).getByRole("link", { name: "프로젝트 · DAW" })).toHaveAttribute("aria-current", "page");
    expect(within(mobile).getByText("DAW")).toBeInTheDocument();
  });

  it("/studio를 생성 workflow로 유지하고 /projects secondary CTA를 제공한다", () => {
    renderShell(<StudioWorkspace />);

    expect(screen.getByText("새 음악 생성")).toBeVisible();
    expect(screen.getByText("어떤 음악을 만들까요?")).toBeVisible();
    expect(screen.getByRole("button", { name: "가사 준비하기" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "프로젝트에서 편집하기" })).toHaveAttribute("href", "/projects");
    expect(screen.getByRole("navigation", { name: "주요 메뉴" }).querySelector('a[href="/studio"]')).toHaveAttribute("aria-current", "page");
  });
});
