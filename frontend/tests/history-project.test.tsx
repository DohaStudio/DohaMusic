import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HistoryList } from "@/features/history/history-list";
import { ProjectList } from "@/features/projects/project-list";
import { dohaApi } from "@/services/doha-api";
import { useHistoryStore } from "@/stores/history-store";
import { useProjectStore } from "@/stores/project-store";

vi.mock("next/link", () => ({ default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={String(href)} {...props}>{children}</a> }));
vi.mock("@/services/doha-api", () => ({ dohaApi: { getHistory: vi.fn(), getProjects: vi.fn(), createProject: vi.fn(), updateProject: vi.fn(), deleteProject: vi.fn(), getPipelineFiles: vi.fn() } }));

describe("History and Projects", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHistoryStore.setState({ items: [], loading: false, error: undefined, query: "", status: "" });
    useProjectStore.setState({ items: [], loading: false, error: undefined });
  });

  it("shows history empty state and applies title search", async () => {
    vi.mocked(dohaApi.getHistory).mockResolvedValue([]);
    render(<HistoryList />);
    expect(await screen.findByText("아직 만든 음악이 없습니다.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("제목 검색"), { target: { value: "dance" } });
    fireEvent.click(screen.getByRole("button", { name: "검색" }));
    await waitFor(() => expect(dohaApi.getHistory).toHaveBeenLastCalledWith(expect.objectContaining({ q: "dance" })));
  });

  it("creates a project and reloads the list", async () => {
    vi.mocked(dohaApi.getProjects).mockResolvedValue([]);
    vi.mocked(dohaApi.createProject).mockResolvedValue({ id: "p", title: "Album", description: null, created_at: "2026-07-31", updated_at: "2026-07-31", job_count: 0 });
    render(<ProjectList />);
    fireEvent.change(screen.getByLabelText("새 프로젝트 이름"), { target: { value: "Album" } });
    fireEvent.click(screen.getByRole("button", { name: "프로젝트 만들기" }));
    await waitFor(() => expect(dohaApi.createProject).toHaveBeenCalledWith({ title: "Album", description: undefined }));
  });

  it("History에 K-POP 설정 요약을 안전하게 표시한다", async () => {
    vi.mocked(dohaApi.getHistory).mockResolvedValue([{
      job_id: "job", project_id: "project", title: "Dance", status: "COMPLETED", created_at: "2026-07-31", duration: 30, voice_profile_name: "Voice", has_audio: false, can_cancel: false, can_retry: false, retry_of_job_id: "source",
      generation_options: { preset_id: "kpop_dance", requested_bpm: 124, hook: { phrase: "Play My Heart", style: "title_repeat", repeat_count: 3 }, vocal_energy: "medium", concept: "confident_bright" },
    }]);
    render(<HistoryList />);
    expect(await screen.findByText(/K-POP Dance · 124 BPM 목표 · Hook: Play My Heart/)).toBeInTheDocument();
    expect(screen.getByText(/다시 만든 작업/)).toBeInTheDocument();
  });
});
