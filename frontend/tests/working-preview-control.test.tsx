import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkingPreviewControl } from "@/features/composition/working-preview-control";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { usePlayerStore } from "@/stores/player-store";
import type { WorkspaceJobDetailDto, WorkspaceJobStatusDto } from "@/types/api";

beforeEach(() => {
  vi.restoreAllMocks();
  usePlayerStore.getState().reset();
});

describe("Working Preview control", () => {
  it("explicit POST에서 current revision을 보내고 exact output을 Global Player에 전달하되 auto-play하지 않는다", async () => {
    const create = vi.spyOn(dohaApi, "createWorkingPreview").mockResolvedValue(preview("job-1", 7));
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue(job("job-1", "succeeded"));
    const user = userEvent.setup();
    renderControl({ revision: 7 });
    expect(create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText("재생 준비됨");
    expect(create).toHaveBeenCalledWith("project-1", 7, expect.any(String));
    expect(usePlayerStore.getState().currentFile).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Working Preview revision 7 재생" }));
    expect(usePlayerStore.getState().currentFile).toMatchObject({
      id: "artifact-job-1",
      contentUrl: "/backend/api/v1/artifacts/artifact-job-1/content",
      fileType: "Working Preview · revision 7",
    });
    expect(usePlayerStore.getState().shouldPlay).toBe(true);
  });

  it("response loss retry는 동일 Idempotency-Key를 재사용한다", async () => {
    const create = vi.spyOn(dohaApi, "createWorkingPreview")
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "lost"))
      .mockResolvedValueOnce(preview("job-1", 3));
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue(job("job-1", "running"));
    const user = userEvent.setup();
    renderControl({ revision: 3 });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText("렌더링 중");
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[0][2]).toBe(create.mock.calls[1][2]);
  });

  it("edit revision이 달라지면 prior Preview를 유지하며 stale과 rerender action을 표시한다", async () => {
    vi.spyOn(dohaApi, "createWorkingPreview")
      .mockResolvedValueOnce(preview("job-1", 4))
      .mockResolvedValueOnce(preview("job-2", 5));
    vi.spyOn(dohaApi, "getWorkspaceJob")
      .mockResolvedValueOnce(job("job-1", "succeeded"))
      .mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    const view = renderControl({ revision: 4 });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText("재생 준비됨");
    view.rerender(wrapper(5));
    expect(await screen.findByText("Preview가 최신 편집본과 다릅니다.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Working Preview revision 4 재생" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Preview 다시 만들기" }));
    await screen.findByText("대기 중");
    expect(vi.mocked(dohaApi.createWorkingPreview).mock.calls[0][2])
      .not.toBe(vi.mocked(dohaApi.createWorkingPreview).mock.calls[1][2]);
    expect(screen.getByRole("button", { name: "Working Preview revision 4 재생" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Preview 다시 만들기" })).toBeDisabled();
  });

  it("revision conflict는 GET reconcile callback 후 자동 Preview 재시도하지 않는다", async () => {
    const create = vi.spyOn(dohaApi, "createWorkingPreview")
      .mockRejectedValue(new ApiError(409, "WORKING_COMPOSITION_REVISION_CONFLICT", "stale"));
    const reconcile = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderControl({ revision: 8, onRevisionConflict: reconcile });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText(/최신 revision을 확인한 뒤/);
    expect(reconcile).toHaveBeenCalledTimes(1);
    expect(create).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["failed" as const, "실패"],
    ["cancelled" as const, "취소됨"],
  ])("terminal %s 상태를 표시한다", async (status, label) => {
    vi.spyOn(dohaApi, "createWorkingPreview").mockResolvedValue(preview("job-1", 2));
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue(job("job-1", status));
    const user = userEvent.setup();
    renderControl({ revision: 2 });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText(label);
  });

  it("0개 또는 복수 exact output은 성공으로 선택하지 않는다", async () => {
    vi.spyOn(dohaApi, "createWorkingPreview").mockResolvedValue(preview("job-1", 2));
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue({ ...job("job-1", "succeeded"), outputs: [] });
    const user = userEvent.setup();
    renderControl({ revision: 2 });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByText("Preview 결과를 안전하게 재생할 수 없습니다.");
    expect(screen.queryByRole("button", { name: /Working Preview revision .* 재생/ })).not.toBeInTheDocument();
  });

  it("Artifact playback 오류는 expired/unavailable로 표시하고 rerender action을 유지한다", async () => {
    vi.spyOn(dohaApi, "createWorkingPreview").mockResolvedValue(preview("job-1", 2));
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue(job("job-1", "succeeded"));
    const user = userEvent.setup();
    renderControl({ revision: 2 });
    await user.click(screen.getByRole("button", { name: "Working Preview 만들기" }));
    await user.click(await screen.findByRole("button", { name: "Working Preview revision 2 재생" }));
    act(() => usePlayerStore.getState().setError("content expired"));
    expect(await screen.findByText(/만료되었거나 사용할 수 없습니다/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Working Preview revision 2 재생" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Preview 다시 만들기" })).toBeEnabled();
  });

  it("WorkingComposition은 있어도 Clip이 없으면 Preview action을 비활성화한다", () => {
    renderControl({ revision: 0, clipCount: 0 });
    expect(screen.getByRole("button", { name: "Working Preview 만들기" })).toBeDisabled();
    expect(screen.getByText("활성 Clip을 배치하면 Preview를 만들 수 있습니다.")).toBeVisible();
  });
});

function renderControl({
  revision,
  clipCount = 1,
  onRevisionConflict = vi.fn().mockResolvedValue(undefined),
}: {
  revision: number;
  clipCount?: number;
  onRevisionConflict?: () => Promise<void>;
}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <WorkingPreviewControl projectId="project-1" workingCompositionId="working-1" currentRevision={revision} clipCount={clipCount} onRevisionConflict={onRevisionConflict} />
    </QueryClientProvider>,
  );
}

function wrapper(revision: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}><WorkingPreviewControl projectId="project-1" workingCompositionId="working-1" currentRevision={revision} clipCount={1} onRevisionConflict={vi.fn().mockResolvedValue(undefined)} /></QueryClientProvider>;
}

function preview(jobId: string, revision: number) {
  return { job_id: jobId, preview_render_id: `render-${jobId}`, working_composition_id: "working-1", rendered_revision: revision, status: "queued" as const, replayed: false };
}

function job(jobId: string, status: WorkspaceJobStatusDto): WorkspaceJobDetailDto {
  return {
    job_id: jobId, project_id: "project-1", composition_snapshot_id: null,
    job_type: "working_preview", status, provider_id: null, model_manifest_id: null,
    progress_percent: null, stage: null, retry_of_job_id: null,
    created_at: "2026-08-29T00:00:00Z", started_at: null, completed_at: status === "succeeded" ? "2026-08-29T00:00:01Z" : null,
    inputs: [],
    outputs: status === "succeeded" ? [{ output_role: "working_preview", output_order: 0, asset_version_id: null, artifact_id: `artifact-${jobId}` }] : [],
    model_usages: [],
    error_code: status === "failed" ? "WORKING_PREVIEW_SOURCE_UNAVAILABLE" : null,
    error_message: status === "failed" ? "raw path must not render" : null,
    error_retryable: status === "failed", error_details_id: null,
  };
}
