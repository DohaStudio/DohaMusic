import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkingCompositionEditor } from "@/features/composition/working-composition-editor";
import type { MediaSourceResolver } from "@/features/composition/working-waveform";
import type { WaveformLoader } from "@/features/composition/waveform";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import type { CompositionReadItemDto, WorkingCompositionDto } from "@/types/api";

afterEach(() => vi.restoreAllMocks());

describe("WorkingComposition editor", () => {
  it("Clip waveform loading, ready와 same-source decode dedup을 표시한다", async () => {
    const clips = [
      { ...working.clips[0], clip_id: "clip-left", source_out: "5.000", source_duration: "10.000" },
      { ...working.clips[0], clip_id: "clip-right", timeline_start: "5.000", source_in: "5.000", source_duration: "10.000" },
    ];
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue({ ...working, clips });
    let finish!: (peaks: number[]) => void;
    const loader = vi.fn<WaveformLoader>(() => new Promise((resolve) => { finish = resolve; }));
    const resolver = vi.fn<MediaSourceResolver>().mockResolvedValue(mediaSource);
    renderEditor({ resolver, loader });
    expect((await screen.findByTestId("clip-waveform-clip-left")).dataset.waveformStatus).toBe("loading");
    finish([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9, 1]);
    await waitFor(() => expect(screen.getByTestId("clip-waveform-clip-left")).toHaveAttribute("data-waveform-status", "ready"));
    expect(screen.getByTestId("clip-waveform-clip-left").dataset.waveformSignature)
      .not.toBe(screen.getByTestId("clip-waveform-clip-right").dataset.waveformSignature);
    expect(resolver).toHaveBeenCalledTimes(1);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("move는 source projection을 유지하고 trim preview와 zoom은 projection/geometry만 갱신한다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue(working);
    const loader = vi.fn<WaveformLoader>().mockResolvedValue([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9, 1]);
    renderEditor({ loader });
    const waveform = await screen.findByTestId("clip-waveform-clip-1");
    await waitFor(() => expect(waveform).toHaveAttribute("data-waveform-status", "ready"));
    const clip = screen.getByRole("button", { name: /Clip clip-1 선택 및 이동/ });
    const initialSignature = waveform.dataset.waveformSignature;
    const initialLeft = clip.style.left;
    fireEvent.pointerDown(clip, { pointerId: 11, clientX: 100 });
    fireEvent.pointerMove(clip, { pointerId: 11, clientX: 164 });
    expect(clip.style.left).not.toBe(initialLeft);
    expect(waveform.dataset.waveformSignature).toBe(initialSignature);
    fireEvent.pointerCancel(clip, { pointerId: 11, clientX: 164 });

    const start = screen.getByLabelText("Clip clip-1 시작 Trim");
    fireEvent.pointerDown(start, { pointerId: 12, clientX: 100 });
    fireEvent.pointerMove(clip, { pointerId: 12, clientX: 164 });
    expect(waveform.dataset.sourceWindow).toBe("1.000:10.000");
    expect(waveform.dataset.waveformSignature).not.toBe(initialSignature);
    fireEvent.pointerCancel(clip, { pointerId: 12, clientX: 164 });

    const widthBeforeZoom = clip.style.width;
    fireEvent.click(screen.getByRole("button", { name: "Clip Timeline 확대" }));
    expect(clip.style.width).not.toBe(widthBeforeZoom);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("split child projection과 unsplit/delete/restore 원본 projection을 derived state로 복원한다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue(working);
    const loader = vi.fn<WaveformLoader>().mockResolvedValue([0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9, 1]);
    const { client } = renderEditor({ loader });
    const original = await screen.findByTestId("clip-waveform-clip-1");
    await waitFor(() => expect(original).toHaveAttribute("data-waveform-status", "ready"));
    const originalSignature = original.dataset.waveformSignature;
    const split = {
      ...working,
      revision: 3,
      clips: [
        { ...working.clips[0], clip_id: "clip-left", source_out: "5.000", split_from_clip_id: "clip-1" },
        { ...working.clips[0], clip_id: "clip-right", timeline_start: "5.000", source_in: "5.000", split_from_clip_id: "clip-1" },
      ],
    };
    act(() => client.setQueryData(["working-composition", "project-1"], split));
    const left = await screen.findByTestId("clip-waveform-clip-left");
    const right = await screen.findByTestId("clip-waveform-clip-right");
    expect(left.dataset.waveformSignature).not.toBe(right.dataset.waveformSignature);
    expect(screen.queryByTestId("clip-waveform-clip-1")).not.toBeInTheDocument();

    act(() => client.setQueryData(["working-composition", "project-1"], { ...working, revision: 4 }));
    await waitFor(() => expect(screen.getByTestId("clip-waveform-clip-1").dataset.waveformSignature).toBe(originalSignature));
    act(() => client.setQueryData(["working-composition", "project-1"], { ...working, revision: 5, clips: [] }));
    await waitFor(() => expect(screen.queryByTestId("clip-waveform-clip-1")).not.toBeInTheDocument());
    act(() => client.setQueryData(["working-composition", "project-1"], { ...working, revision: 6 }));
    await waitFor(() => expect(screen.getByTestId("clip-waveform-clip-1").dataset.waveformSignature).toBe(originalSignature));
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("resolver/decode failure를 unavailable로 격리해 Clip 편집 controls를 유지한다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue(working);
    renderEditor({ loader: vi.fn<WaveformLoader>().mockRejectedValue(new Error("secret decode")) });
    await waitFor(() => expect(screen.getByTestId("clip-waveform-clip-1")).toHaveAttribute("data-waveform-status", "unavailable"));
    expect(screen.getByRole("button", { name: /Clip clip-1 선택 및 이동/ })).toBeEnabled();
    expect(screen.queryByText("secret decode")).not.toBeInTheDocument();
  });

  it("GET no-data에서 자동 생성하지 않고 explicit initialize 후 revision을 reconcile한다", async () => {
    const get = vi.spyOn(dohaApi, "getWorkingComposition")
      .mockRejectedValueOnce(new ApiError(404, "WORKING_COMPOSITION_NOT_FOUND", "missing"))
      .mockResolvedValueOnce(emptyWorking);
    const initialize = vi.spyOn(dohaApi, "initializeWorkingComposition")
      .mockResolvedValue({ working_composition_id: "working-1", completed_revision: 0, replayed: false });
    const user = userEvent.setup();
    renderEditor();
    expect(await screen.findByText(/아직 WorkingComposition이 없습니다/)).toBeVisible();
    expect(initialize).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "WorkingComposition 시작" }));
    expect(await screen.findByText("편집 공간을 시작했습니다. revision 0")).toBeVisible();
    expect(get).toHaveBeenCalledTimes(2);
    expect(initialize.mock.calls[0][1]).toMatch(/[0-9a-f-]{36}/);
  });

  it("initialize response loss retry는 동일 Idempotency-Key를 재사용한다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition")
      .mockRejectedValueOnce(new ApiError(404, "WORKING_COMPOSITION_NOT_FOUND", "missing"))
      .mockResolvedValueOnce(emptyWorking);
    const initialize = vi.spyOn(dohaApi, "initializeWorkingComposition")
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "lost"))
      .mockResolvedValueOnce({ working_composition_id: "working-1", completed_revision: 0, replayed: true });
    const user = userEvent.setup();
    renderEditor();
    await user.click(await screen.findByRole("button", { name: "WorkingComposition 시작" }));
    await screen.findByText("편집 공간을 시작했습니다. revision 0");
    expect(initialize).toHaveBeenCalledTimes(2);
    expect(initialize.mock.calls[0][1]).toBe(initialize.mock.calls[1][1]);
  });

  it("여러 move pointermove는 preview만 하고 pointerup에서 mutation 한 번 호출한다", async () => {
    const afterMove = { ...working, revision: 3, clips: [{ ...working.clips[0], timeline_start: "2.000" }] };
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValueOnce(working).mockResolvedValueOnce(afterMove);
    const move = vi.spyOn(dohaApi, "moveWorkingClip").mockResolvedValue({ clip_id: "clip-1", completed_revision: 3, replayed: false });
    renderEditor();
    const clip = await screen.findByRole("button", { name: /Clip clip-1 선택 및 이동/ });
    fireEvent.pointerDown(clip, { pointerId: 1, clientX: 100 });
    fireEvent.pointerMove(clip, { pointerId: 1, clientX: 164 });
    fireEvent.pointerMove(clip, { pointerId: 1, clientX: 228 });
    expect(move).not.toHaveBeenCalled();
    fireEvent.pointerUp(clip, { pointerId: 1, clientX: 228 });
    await waitFor(() => expect(move).toHaveBeenCalledTimes(1));
    expect(move.mock.calls[0][2]).toMatchObject({ expected_revision: 2, timeline_start: "2.000" });
  });

  it("pointercancel은 Clip move mutation을 만들지 않는다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue(working);
    const move = vi.spyOn(dohaApi, "moveWorkingClip");
    renderEditor();
    const clip = await screen.findByRole("button", { name: /Clip clip-1 선택 및 이동/ });
    fireEvent.pointerDown(clip, { pointerId: 2, clientX: 100 });
    fireEvent.pointerMove(clip, { pointerId: 2, clientX: 164 });
    fireEvent.pointerCancel(clip, { pointerId: 2, clientX: 164 });
    expect(move).not.toHaveBeenCalled();
  });

  it("revision conflict는 GET reconcile하고 Undo/Redo 버튼을 비운다", async () => {
    const renamed = { ...working, revision: 3, tracks: [{ ...working.tracks[0], name: "Renamed" }] };
    const external = { ...renamed, revision: 7, tracks: [{ ...working.tracks[0], name: "External" }] };
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValueOnce(working).mockResolvedValueOnce(renamed).mockResolvedValueOnce(external);
    vi.spyOn(dohaApi, "renameWorkingTrack")
      .mockResolvedValueOnce({ track_id: "track-1", completed_revision: 3, replayed: false })
      .mockRejectedValueOnce(new ApiError(409, "WORKING_COMPOSITION_REVISION_CONFLICT", "stale"));
    const user = userEvent.setup();
    renderEditor();
    const input = await screen.findByLabelText("Track 1 Track 이름");
    await user.clear(input);
    await user.type(input, "Renamed");
    fireEvent.blur(input);
    await waitFor(() => expect(screen.getByRole("button", { name: "편집 실행 취소" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "편집 실행 취소" }));
    expect(await screen.findByText(/Undo\/Redo 기록은 초기화/)).toBeVisible();
    expect(screen.getByRole("button", { name: "편집 실행 취소" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "편집 다시 실행" })).toBeDisabled();
    expect(screen.getByText(/revision 7/)).toBeVisible();
  });

  it("checkout 성공은 history barrier로 Undo/Redo stack을 비운다", async () => {
    const renamed = { ...working, revision: 3, tracks: [{ ...working.tracks[0], name: "Renamed" }] };
    const checkedOut = { ...emptyWorking, revision: 4, base_composition_snapshot_id: "snapshot-1" };
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValueOnce(working).mockResolvedValueOnce(renamed).mockResolvedValueOnce(checkedOut);
    vi.spyOn(dohaApi, "renameWorkingTrack").mockResolvedValue({ track_id: "track-1", completed_revision: 3, replayed: false });
    vi.spyOn(dohaApi, "checkoutWorkingComposition").mockResolvedValue({ working_composition_id: "working-1", base_composition_snapshot_id: "snapshot-1", completed_revision: 4, replayed: false });
    const user = userEvent.setup();
    renderEditor();
    const input = await screen.findByLabelText("Track 1 Track 이름");
    await user.clear(input);
    await user.type(input, "Renamed");
    fireEvent.blur(input);
    await waitFor(() => expect(screen.getByRole("button", { name: "편집 실행 취소" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "현재 Snapshot Checkout" }));
    await waitFor(() => expect(screen.getByText(/revision 4/)).toBeVisible());
    expect(screen.getByRole("button", { name: "편집 실행 취소" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "편집 다시 실행" })).toBeDisabled();
  });

  it("Preview 생성 성공은 편집 revision과 Undo/Redo history를 변경하지 않는다", async () => {
    vi.spyOn(dohaApi, "getWorkingComposition").mockResolvedValue(working);
    vi.spyOn(dohaApi, "createWorkingPreview").mockResolvedValue({
      job_id: "job-preview", preview_render_id: "render-preview",
      working_composition_id: "working-1", rendered_revision: 2,
      status: "queued", replayed: false,
    });
    vi.spyOn(dohaApi, "getWorkspaceJob").mockResolvedValue({
      job_id: "job-preview", job_type: "working_preview_render", status: "succeeded",
      project_id: "project-1", composition_snapshot_id: null,
      provider_id: null, model_manifest_id: null, progress_percent: 100,
      stage: null, retry_of_job_id: null,
      inputs: [],
      outputs: [{ output_role: "working_preview", output_order: 0, artifact_id: "artifact-preview", asset_version_id: "version-preview" }],
      model_usages: [],
      error_code: null, error_message: null, error_retryable: null, error_details_id: null,
      created_at: "2026-08-29T00:00:00Z", started_at: "2026-08-29T00:00:01Z",
      completed_at: "2026-08-29T00:00:02Z",
    });
    const user = userEvent.setup();
    renderEditor();
    await user.click(await screen.findByRole("button", { name: "Working Preview 만들기" }));
    await screen.findByRole("button", { name: "Working Preview revision 2 재생" });
    expect(screen.getByText("revision 2 · 저장됨 · Undo/Redo는 이 탭의 메모리에만 유지")).toBeVisible();
    expect(screen.getByRole("button", { name: "편집 실행 취소" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "편집 다시 실행" })).toBeDisabled();
  });
});

function renderEditor({
  resolver = vi.fn<MediaSourceResolver>().mockResolvedValue(mediaSource),
  loader = vi.fn<WaveformLoader>().mockResolvedValue([0.2, 0.8]),
}: { resolver?: MediaSourceResolver; loader?: WaveformLoader } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return {
    ...render(<QueryClientProvider client={client}><WorkingCompositionEditor projectId="project-1" snapshotId="snapshot-1" sources={[source]} mediaSourceResolver={resolver} waveformLoader={loader} /></QueryClientProvider>),
    client,
  };
}

const emptyWorking: WorkingCompositionDto = {
  working_composition_id: "working-1", project_id: "project-1", base_composition_snapshot_id: null,
  revision: 0, mix_settings: {}, tracks: [], clips: [], timeline_duration: "0",
};
const working: WorkingCompositionDto = {
  ...emptyWorking,
  revision: 2,
  tracks: [{ track_id: "track-1", track_type: "audio", name: "Track 1", track_order: 0 }],
  clips: [{ clip_id: "clip-1", track_id: "track-1", source_asset_version_id: "version-1", timeline_start: "0.000", source_in: "0.000", source_out: "10.000", source_duration: "10.000", split_from_clip_id: null }],
  timeline_duration: "10.000",
};
const source: CompositionReadItemDto = {
  snapshot_item_id: "item-1", item_role: "music", sort_order: 0,
  asset_version: { asset_version_id: "version-1", asset_id: "asset-1", version_number: 1, version_origin: "provider", parent_asset_version_id: null, processing_chain_id: null, provider_id: null, model_manifest_id: null, settings_snapshot: {}, created_at: "2026-08-26T00:00:00Z" },
  artifacts: [],
};
const mediaSource = {
  asset_version_id: "version-1", artifact_id: "artifact-1", media_type: "audio/wav" as const,
  size_bytes: 48, artifact_checksum: "a".repeat(64), duration_seconds: "10",
  content_url: "/api/v1/artifacts/artifact-1/content",
};
