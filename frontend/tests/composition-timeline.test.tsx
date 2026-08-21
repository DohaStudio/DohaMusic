import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompositionTimeline } from "@/features/composition/composition-timeline";
import type { CompositionPlaybackResolution } from "@/features/composition/timeline-playback";
import {
  clampTimelineTime,
  resolveCompositionPlayback,
  timelineTimeFromPointer,
} from "@/features/composition/timeline-playback";
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

const available = { status: "available" as const, source };
const unavailable = {
  status: "unavailable" as const,
  code: "NO_CANONICAL_PLAYBACK_SOURCE" as const,
  reason: "단일 Mix source가 없습니다.",
};

function renderTimeline(playback: CompositionPlaybackResolution = available) {
  return render(
    <>
      <CompositionTimeline tracks={tracks} playback={playback} />
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
  });

  it("time ruler와 snapshot-local Track lane을 표시한다", () => {
    renderTimeline(unavailable);
    expect(screen.getByRole("heading", { name: "Composition Timeline" })).toBeVisible();
    expect(screen.getByLabelText("초 단위 Timeline ruler")).toBeVisible();
    expect(screen.getByRole("list", { name: "Composition Track lanes" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Mix 1에서/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /Vocal 2에서/ })).toBeVisible();
    expect(screen.queryByText(/Waveform/)).not.toBeInTheDocument();
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

  it("media currentTime으로 Playhead와 시간 표시를 갱신하고 ended를 처리한다", () => {
    const { container } = renderTimeline();
    const audio = loadAudio(container);
    act(() => usePlayerStore.getState().play(source));
    Object.defineProperty(audio, "currentTime", { value: 12, writable: true, configurable: true });
    fireEvent.timeUpdate(audio);
    expect(screen.getByLabelText("현재 재생 시간과 전체 길이")).toHaveTextContent("0:12 / 0:30");
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
    const viewport = screen.getByTestId("timeline-scroll");
    vi.spyOn(viewport, "getBoundingClientRect").mockReturnValue({
      left: 100, right: 900, top: 0, bottom: 300, width: 800, height: 300,
      x: 100, y: 0, toJSON: () => ({}),
    });
    await user.click(screen.getByRole("button", { name: "Timeline 확대" }));
    expect(screen.getByLabelText("Timeline 배율")).toHaveTextContent("80px/s");
    fireEvent.click(screen.getByLabelText("초 단위 Timeline ruler"), { clientX: 424 });
    expect(usePlayerStore.getState().currentTime).toBe(2);
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
