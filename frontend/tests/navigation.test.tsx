import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell";
import { StudioWorkspace } from "@/features/studio/studio-workspace";
import { useStudioStore } from "@/stores/studio-store";

let pathname = "/studio";
let search = "";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(search),
}));
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
    search = "";
    useStudioStore.getState().reset();
  });

  it("Desktop과 Mobile에서 Project와 DAW를 별도 link로 제공한다", () => {
    renderShell();

    const desktop = screen.getByRole("navigation", { name: "주요 메뉴" });
    const mobile = screen.getByRole("navigation", { name: "모바일 메뉴" });
    expect(within(desktop).getByRole("link", { name: "DAW 편집" })).toHaveAttribute("href", "/projects?mode=daw");
    expect(within(desktop).getByRole("link", { name: "프로젝트" })).toHaveAttribute("href", "/projects");
    expect(within(mobile).getByRole("link", { name: "DAW 편집" })).toBeVisible();
    expect(within(mobile).getByRole("link", { name: "프로젝트" })).toBeVisible();
  });

  it("normal Project, DAW intent, nested Project에서 하나의 entry만 active로 표시한다", () => {
    pathname = "/projects";
    const view = renderShell();
    const desktop = screen.getByRole("navigation", { name: "주요 메뉴" });
    expect(within(desktop).getByRole("link", { name: "프로젝트" })).toHaveAttribute("aria-current", "page");
    expect(within(desktop).getByRole("link", { name: "DAW 편집" })).not.toHaveAttribute("aria-current");

    search = "mode=daw";
    view.rerender(<AppShell><div>Content</div></AppShell>);
    expect(within(desktop).getByRole("link", { name: "DAW 편집" })).toHaveAttribute("aria-current", "page");
    expect(within(desktop).getByRole("link", { name: "프로젝트" })).not.toHaveAttribute("aria-current");

    pathname = "/projects/project-1";
    search = "";
    view.rerender(<AppShell><div>Content</div></AppShell>);
    expect(within(desktop).getByRole("link", { name: "DAW 편집" })).toHaveAttribute("aria-current", "page");
    expect(within(desktop).getByRole("link", { name: "프로젝트" })).not.toHaveAttribute("aria-current");
  });

  it("/studio를 생성 workflow로 유지하고 /projects secondary CTA를 제공한다", () => {
    renderShell(<StudioWorkspace />);

    expect(screen.getByText("새 음악 생성")).toBeVisible();
    expect(screen.getByText("어떤 음악을 만들까요?")).toBeVisible();
    expect(screen.getByRole("button", { name: "가사 준비하기" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "DAW에서 편집하기" })).toHaveAttribute("href", "/projects?mode=daw");
    expect(screen.getByRole("navigation", { name: "주요 메뉴" }).querySelector('a[href="/studio"]')).toHaveAttribute("aria-current", "page");
  });
});
