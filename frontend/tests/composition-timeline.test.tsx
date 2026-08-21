import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompositionTimeline } from "@/features/composition/composition-timeline";
import type { CompositionPlaybackResolution } from "@/features/composition/timeline-playback";
import {
  clampTimelineTime,
  formatTimelinePreciseTime,
  resolveCompositionPlayback,
  timelinePixelsToTime,
  timelineTimeToPixels,
  timelineTimeFromPointer,
} from "@/features/composition/timeline-playback";
import type { WaveformLoader } from "@/features/composition/waveform";
import { GlobalPlayer } from "@/features/player/global-player";
import { usePlayerStore } from "@/stores/player-store";
import type { CompositionWorkspaceDto } from "@/types/api";
import type { SafePipelineFile } from "@/types/domain";

const tracks = [
  {
    projection_id: "track-mix",
    identity_scope: "snapshot" as const,
    snapshot_item_id: "item-mix",
    item_role: "mix" as const,
    sort_order: 0,
    asset_id: "asset-mix",
    asset_version_id: "version-mix",
  },
  {
    projection_id: "track-vocal",
    identity_scope: "snapshot" as const,
    snapshot_item_id: "item-vocal",
    item_role: "vocal" as const,
    sort_order: 1,
    asset_id: "asset-vocal",
    asset_version_id: "version-vocal",
  },
];

const source: SafePipelineFile = {
  id: "artifact-mix",
  jobId: "snapshot-1",
  fileType: "Composition Mix · audio",
  mimeType: "audio/wav",
  createdAt: "2026-08-21T00:00:00Z",
  contentAvailable: true,
  downloadAvailable: true,
  contentUrl: "/backend/api/v1/artifacts/artifact-mix/content",
  downloadUrl: "/backend/api/v1/artifacts/artifact-mix/download",
};

const waveformSource = {
  cacheKey: "artifact-mix:checksum",
  contentUrl: source.contentUrl!,
  mediaType: source.mimeType,
  sizeBytes: 100,
};
const available = { status: "available" as const, source, waveformSource };
const unavailable = {
  status: "unavailable" as const,
  code: "NO_CANONICAL_PLAYBACK_SOURCE" as const,
  reason: "단일 Mix source가 없습니다.",
};

const waveformLoader = vi.fn<WaveformLoader>();

function renderTimeline(
  playback: CompositionPlaybackResolution = available,
  loader: WaveformLoader = waveformLoader,
) {
  return render(
    <>
      <CompositionTimeline tracks={tracks} playback={playback} waveformLoader={loader} />
      <GlobalPlayer />
    </>,
  );
}

function loadAudio(container: HTMLElement, duration = 30) {
  const audio = container.querySelector("audio")!;
  Object.defineProperty(audio, "duration", { value: duration, configurable: true });
  fireEvent.loadedMetadata(audio);
  return audio;
}

describe("Timeline Playback Foundation", () => {
  beforeEach(() => {
    usePlayerStore.getState().reset();
    vi.restoreAllMocks();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    waveformLoader.mockReset();
    waveformLoader.mockResolvedValue([0.25, 0.75, 1, 0.4]);
  });

  it("time ruler와 snapshot-local Track lane을 표시한다", () => {
    renderTimeline(unavailable);
    expect(screen.getByRole("heading", { name: "Composition Timeline" })).toBeVisible();
    expect(screen.getByLabelText("초 단위 Timeline ruler")).toBeVisible();
    expect(screen.getByRole("list", { name: "Composition Track lanes" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Mix 1에서/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /Vocal 2에서/ })).toBeVisible();
    expect(screen.getByText("Master / Mix")).toBeVisible();
    expect(screen.getByText("Waveform source를 사용할 수 없습니다.")).toBeVisible();
  });

  it("canonical source가 없으면 명시적 unavailable 상태로 transport를 비활성화한다", () => {
    renderTimeline(unavailable);
    expect(screen.getByText("NO_CANONICAL_PLAYBACK_SOURCE")).toBeVisible();
    expect(screen.getByRole("button", { name: "Timeline 재생" })).toBeDisabled();
    expect(screen.getByText(/길이 확인 전/)).toBeVisible();
  });

  it("Track 선택을 local UI 상태로 유지한다", async () => {
    const user = userEvent.setup();
    renderTimeline(unavailable);
    const mix = screen.getByRole("button", { name: /Mix 1$/ });
    const vocal = screen.getByRole("button", { name: /Vocal 2$/ });
    expect(mix).toHaveAttribute("aria-pressed", "true");
    await user.click(vocal);
    expect(vocal).toHaveAttribute("aria-pressed", "true");
    expect(mix).toHaveAttribute("aria-pressed", "false");
  });

  it("Global Player 하나를 통해 play와 pause를 동기화한다", async () => {
    const user = userEvent.setup();
    const { container } = renderTimeline();
    loadAudio(container);
    await user.click(screen.getByRole("button", { name: "Timeline 재생" }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Timeline 일시정지" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Timeline 일시정지" }));
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  });

  it("media currentTime으로 Playhead와 정밀 시간 표시를 갱신하고 ended를 처리한다", () => {
    const { container } = renderTimeline();
    const audio = loadAudio(container);
    act(() => usePlayerStore.getState().play(source));
    Object.defineProperty(audio, "currentTime", { value: 12, writable: true, configurable: true });
    fireEvent.timeUpdate(audio);
    expect(screen.getByLabelText("현재 재생 시간과 전체 길이")).toHaveTextContent("0:12.000 / 0:30");
    expect(container.querySelector(".timeline-playhead")).toHaveStyle({ left: "932px" });
    fireEvent.ended(audio);
    expect(usePlayerStore.getState().shouldPlay).toBe(false);
    expect(usePlayerStore.getState().currentTime).toBe(30);
  });

  it("viewport offset과 horizontal scroll을 반영해 click-to-seek한다", () => {
    const { container } = renderTimeline();
    loadAudio(container);
    const viewport = screen.getByTestId("timeline-scroll");
    Object.defineProperty(viewport, "scrollLeft", { value: 128, writable: true });
    vi.spyOn(viewport, "getBoundingClientRect").mockReturnValue({
      left: 100, right: 900, top: 0, bottom: 300, width: 800, height: 300,
      x: 100, y: 0, toJSON: () => ({}),
    });
    fireEvent.click(screen.getByLabelText("초 단위 Timeline ruler"), { clientX: 328 });
    expect(usePlayerStore.getState().currentTime).toBe(3);
  });

  it("zoom 후 변경된 scale로 seek 좌표를 계산한다", async () => {
    const user = userEvent.setup();
    const { container } = renderTimeline();
    loadAudio(container);
    const canvas = container.querySelector(".timeline-canvas");
    const viewport = screen.getByTestId("timeline-scroll");
    vi.spyOn(viewport, "getBoundingClientRect").mockReturnValue({
      left: 100, right: 900, top: 0, bottom: 300, width: 800, height: 300,
      x: 100, y: 0, toJSON: () => ({}),
    });
    await user.click(screen.getByRole("button", { name: "Timeline 확대" }));
    expect(screen.getByLabelText("Timeline 배율")).toHaveTextContent("80px/s");
    expect(canvas).toHaveStyle({ width: "2564px" });
    fireEvent.click(screen.getByLabelText("초 단위 Timeline ruler"), { clientX: 424 });
    expect(usePlayerStore.getState().currentTime).toBe(2);
    expect(waveformLoader).toHaveBeenCalledTimes(1);
  });

  it("seek를 duration 범위로 clamp한다", () => {
    expect(clampTimelineTime(-3, 30)).toBe(0);
    expect(clampTimelineTime(40, 30)).toBe(30);
    expect(timelineTimeFromPointer({
      clientX: 1000,
      viewportLeft: 100,
      scrollLeft: 200,
      pixelsPerSecond: 10,
      duration: 30,
    })).toBe(30);
    expect(timelineTimeToPixels(2.5, 80)).toBe(200);
    expect(timelinePixelsToTime(200, 80, 30)).toBe(2.5);
    expect(formatTimelinePreciseTime(61.234)).toBe("1:01.234");
  });

  it("Space와 방향키 transport를 지원하고 입력 중 shortcut은 무시한다", () => {
    const { container } = renderTimeline();
    loadAudio(container);
    fireEvent.keyDown(window, { code: "Space" });
    expect(usePlayerStore.getState().shouldPlay).toBe(true);
    act(() => usePlayerStore.getState().seek(10));
    fireEvent.keyDown(window, { code: "ArrowRight" });
    expect(usePlayerStore.getState().currentTime).toBe(15);
    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { code: "Space" });
    expect(usePlayerStore.getState().shouldPlay).toBe(true);
    input.remove();
  });

  it("waveform loading과 bounded ready SVG를 순서대로 표시한다", async () => {
    let resolve!: (peaks: number[]) => void;
    waveformLoader.mockImplementation(() => new Promise((done) => { resolve = done; }));
    renderTimeline();
    expect(screen.getByText("Waveform을 불러오는 중입니다.")).toBeVisible();
    resolve([0.1, 0.4, 1]);
    const waveform = await screen.findByTestId("master-waveform");
    expect(waveform).toHaveAttribute("data-peak-count", "3");
    expect(waveform.querySelectorAll("path")).toHaveLength(1);
  });

  it("waveform decode 실패를 격리하고 기존 playback을 유지한다", async () => {
    waveformLoader.mockRejectedValue(new Error("secret source detail"));
    const user = userEvent.setup();
    const { container } = renderTimeline();
    loadAudio(container);
    expect(await screen.findByText("Waveform을 표시할 수 없습니다. 재생은 계속 사용할 수 있습니다.")).toBeVisible();
    expect(screen.queryByText("secret source detail")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Timeline 재생" }));
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
  });

  it("waveform click이 ruler와 같은 scroll·zoom 좌표계로 seek한다", () => {
    const { container } = renderTimeline();
    loadAudio(container);
    const viewport = screen.getByTestId("timeline-scroll");
    Object.defineProperty(viewport, "scrollLeft", { value: 128, writable: true });
    vi.spyOn(viewport, "getBoundingClientRect").mockReturnValue({
      left: 100, right: 900, top: 0, bottom: 300, width: 800, height: 300,
      x: 100, y: 0, toJSON: () => ({}),
    });
    fireEvent.click(screen.getByRole("button", { name: "Master Mix Waveform에서 재생 위치 선택" }), {
      clientX: 328,
    });
    expect(usePlayerStore.getState().currentTime).toBe(3);
  });

  it("Playhead drag preview를 player seek와 분리하고 pointer up에서 commit한다", () => {
    const { container } = renderTimeline();
    loadAudio(container);
    const viewport = screen.getByTestId("timeline-scroll");
    vi.spyOn(viewport, "getBoundingClientRect").mockReturnValue({
      left: 100, right: 900, top: 0, bottom: 300, width: 800, height: 300,
      x: 100, y: 0, toJSON: () => ({}),
    });
    const handle = screen.getByRole("slider", { name: "Timeline Playhead 재생 위치" });
    fireEvent.pointerDown(handle, { pointerId: 7, clientX: 264 });
    fireEvent.pointerMove(handle, { pointerId: 7, clientX: 424 });
    expect(usePlayerStore.getState().currentTime).toBe(0);
    expect(screen.getByLabelText("현재 재생 시간과 전체 길이")).toHaveTextContent("0:02.500");
    fireEvent.pointerUp(handle, { pointerId: 7, clientX: 424 });
    expect(usePlayerStore.getState().currentTime).toBe(2.5);
  });

  it("source 변경 시 이전 waveform 결과를 폐기한다", async () => {
    const pending = new Map<string, (peaks: number[]) => void>();
    const loader = vi.fn<WaveformLoader>((input) => new Promise((resolve) => {
      pending.set(input.cacheKey, resolve);
    }));
    const view = renderTimeline(available, loader);
    const nextSource = { ...source, id: "artifact-next", contentUrl: "/backend/api/v1/artifacts/artifact-next/content" };
    const next = {
      status: "available" as const,
      source: nextSource,
      waveformSource: {
        ...waveformSource,
        cacheKey: "artifact-next:checksum",
        contentUrl: nextSource.contentUrl!,
      },
    };
    view.rerender(
      <>
        <CompositionTimeline tracks={tracks} playback={next} waveformLoader={loader} />
        <GlobalPlayer />
      </>,
    );
    pending.get("artifact-mix:checksum")?.([1]);
    expect(screen.queryByTestId("master-waveform")).not.toBeInTheDocument();
    pending.get("artifact-next:checksum")?.([0.2, 0.8]);
    expect(await screen.findByTestId("master-waveform")).toHaveAttribute("data-peak-count", "2");
  });

  it("unmount 시 진행 중 waveform fetch를 abort한다", () => {
    let capturedSignal: AbortSignal | undefined;
    const loader = vi.fn<WaveformLoader>((_, signal) => {
      capturedSignal = signal;
      return new Promise(() => undefined);
    });
    const view = renderTimeline(available, loader);
    expect(capturedSignal?.aborted).toBe(false);
    view.unmount();
    expect(capturedSignal?.aborted).toBe(true);
  });

  it("GlobalPlayer audio element 하나와 접근 가능한 seek controls만 사용한다", () => {
    const { container } = renderTimeline();
    loadAudio(container);
    expect(container.querySelectorAll("audio")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "초 단위 Timeline ruler" })).toBeEnabled();
    expect(screen.getByRole("slider", { name: "Timeline Playhead 재생 위치" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("button", { name: "Master Mix Waveform에서 재생 위치 선택" })).toBeEnabled();
  });
});

describe("Composition playback authority", () => {
  const base = {
    state: "ready" as const,
    project: {
      project_id: "project-1",
      workspace_id: "workspace-1",
      title: "Project",
      lifecycle_status: "active",
      created_at: "2026-08-21T00:00:00Z",
      updated_at: "2026-08-21T00:00:00Z",
    },
    selection: {
      selected_snapshot_id: "snapshot-1",
      resolved_snapshot_id: "snapshot-1",
      resolution: "selected" as const,
      is_current: true,
    },
    snapshot: {
      composition_snapshot_id: "snapshot-1",
      project_id: "project-1",
      snapshot_version: 1,
      created_at: "2026-08-21T00:00:00Z",
    },
    items: [],
    track_projections: tracks,
    section_projection: { availability: "not_available" as const, items: [] as [] },
    mix_settings_snapshot: {},
    lineage: { processing_chain_id: null, provider_versions: {}, model_manifest_ids: {} },
  } satisfies CompositionWorkspaceDto;

  const mixItem = {
    snapshot_item_id: "item-mix",
    item_role: "mix" as const,
    sort_order: 0,
    asset_version: {
      asset_version_id: "version-mix",
      asset_id: "asset-mix",
      version_number: 1,
      version_origin: "provider_output",
      parent_asset_version_id: null,
      processing_chain_id: null,
      provider_id: null,
      model_manifest_id: null,
      settings_snapshot: {},
      created_at: "2026-08-21T00:00:00Z",
    },
    artifacts: [{
      artifact_id: "artifact-mix",
      asset_version_id: "version-mix",
      artifact_kind: "audio",
      media_type: "audio/wav",
      size_bytes: 100,
      checksum_algorithm: "sha256",
      artifact_checksum: "a".repeat(64),
      producer_type: "workspace",
      producer_id: null,
      run_id: null,
      retention_status: "active",
      created_at: "2026-08-21T00:00:00Z",
      content_url: "/api/v1/artifacts/artifact-mix/content",
      download_url: "/api/v1/artifacts/artifact-mix/download",
    }],
  };

  it("selected Snapshot의 단일 Mix와 단일 safe audio Artifact만 source로 해석한다", () => {
    const resolution = resolveCompositionPlayback({ ...base, items: [mixItem] });
    expect(resolution.status).toBe("available");
    if (resolution.status === "available") {
      expect(resolution.source.id).toBe("artifact-mix");
      expect(resolution.source.contentUrl).toBe("/backend/api/v1/artifacts/artifact-mix/content");
    }
  });

  it("Mix가 없거나 복수 Audio Artifact이면 first/latest를 고르지 않는다", () => {
    expect(resolveCompositionPlayback(base)).toMatchObject({
      status: "unavailable",
      code: "NO_CANONICAL_PLAYBACK_SOURCE",
    });
    const ambiguous = {
      ...mixItem,
      artifacts: [...mixItem.artifacts, { ...mixItem.artifacts[0], artifact_id: "artifact-2" }],
    };
    expect(resolveCompositionPlayback({ ...base, items: [ambiguous] })).toMatchObject({
      status: "unavailable",
      code: "NO_CANONICAL_PLAYBACK_SOURCE",
    });
  });
});
