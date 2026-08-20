import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompositionWorkspace } from "@/features/composition/composition-workspace";
import { StudioWorkspace } from "@/features/studio/studio-workspace";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import type { CompositionWorkspaceDto } from "@/types/api";

const project = {
  project_id: "project-1",
  workspace_id: "workspace-1",
  title: "테스트 프로젝트",
  lifecycle_status: "active",
  created_at: "2026-08-20T00:00:00Z",
  updated_at: "2026-08-20T00:00:00Z",
};

const base: CompositionWorkspaceDto = {
  state: "empty",
  project,
  selection: {
    selected_snapshot_id: null,
    resolved_snapshot_id: null,
    resolution: "none",
    is_current: false,
  },
  snapshot: null,
  items: [],
  track_projections: [],
  section_projection: { availability: "not_available", items: [] },
  mix_settings_snapshot: {},
  lineage: {
    processing_chain_id: null,
    provider_versions: {},
    model_manifest_ids: {},
  },
};

const selectionRequired: CompositionWorkspaceDto = {
  ...base,
  state: "selection_required",
};

const ready: CompositionWorkspaceDto = {
  ...base,
  state: "ready",
  selection: {
    selected_snapshot_id: "snapshot-1",
    resolved_snapshot_id: "snapshot-1",
    resolution: "selected",
    is_current: true,
  },
  snapshot: {
    composition_snapshot_id: "snapshot-1",
    project_id: "project-1",
    snapshot_version: 7,
    processing_chain_id: "chain-1",
    provider_versions: { music: "1.2.0" },
    model_manifest_ids: { music: "manifest-1" },
    created_at: "2026-08-20T01:00:00Z",
  },
  items: [
    {
      snapshot_item_id: "item-1",
      item_role: "music",
      sort_order: 0,
      asset_version: {
        asset_version_id: "asset-version-exact",
        asset_id: "asset-1",
        version_number: 3,
        version_origin: "provider_output",
        parent_asset_version_id: "asset-version-parent",
        processing_chain_id: "chain-1",
        provider_id: "music-provider",
        model_manifest_id: "manifest-1",
        settings_snapshot: {},
        created_at: "2026-08-20T00:30:00Z",
      },
      artifacts: [
        {
          artifact_id: "artifact-1",
          asset_version_id: "asset-version-exact",
          artifact_kind: "audio",
          media_type: "audio/wav",
          size_bytes: 2048,
          checksum_algorithm: "sha256",
          artifact_checksum: "safe-checksum",
          producer_type: "provider",
          producer_id: "music-provider",
          run_id: "run-1",
          retention_status: "active",
          created_at: "2026-08-20T00:40:00Z",
          content_url: "/api/v1/artifacts/artifact-1/content",
          download_url: "/api/v1/artifacts/artifact-1/download",
        },
      ],
    },
  ],
  track_projections: [
    {
      projection_id: "item-1",
      identity_scope: "snapshot",
      snapshot_item_id: "item-1",
      item_role: "music",
      sort_order: 0,
      asset_id: "asset-1",
      asset_version_id: "asset-version-exact",
    },
  ],
  mix_settings_snapshot: { master_gain_db: -1 },
  lineage: {
    processing_chain_id: "chain-1",
    provider_versions: { music: "1.2.0" },
    model_manifest_ids: { music: "manifest-1" },
  },
};

const snapshots = [
  {
    composition_snapshot_id: "snapshot-1",
    project_id: "project-1",
    snapshot_version: 7,
    created_at: "2026-08-20T01:00:00Z",
  },
];

function renderComposition() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <CompositionWorkspace projectId="project-1" />
    </QueryClientProvider>,
  );
}

describe("D1-B Composition Workspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(dohaApi, "listProjectCompositionSnapshots").mockResolvedValue(snapshots);
    vi.spyOn(dohaApi, "selectProjectComposition").mockResolvedValue({
      project_id: "project-1",
      selected_snapshot_id: "snapshot-1",
    });
  });

  it("empty를 정상 상태로 렌더하고 selector와 ready UI를 숨긴다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(base);
    renderComposition();
    expect(await screen.findByText("아직 Composition Snapshot이 없습니다.")).toBeVisible();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByText("현재 선택")).not.toBeInTheDocument();
  });

  it("selection_required에서 자동 선택과 자동 PATCH를 하지 않는다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(selectionRequired);
    renderComposition();
    const radio = await screen.findByRole("radio", { name: /Snapshot v7/ });
    expect(radio).not.toBeChecked();
    expect(dohaApi.selectProjectComposition).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "선택 적용" })).toBeDisabled();
  });

  it("radio 선택만으로 PATCH하지 않고 명시적 적용 시 PATCH 후 aggregate를 refetch한다", async () => {
    const get = vi
      .spyOn(dohaApi, "getProjectComposition")
      .mockResolvedValueOnce(selectionRequired)
      .mockResolvedValueOnce(ready);
    const user = userEvent.setup();
    renderComposition();
    await user.click(await screen.findByRole("radio", { name: /Snapshot v7/ }));
    expect(dohaApi.selectProjectComposition).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "선택 적용" }));
    await screen.findByText("현재 선택");
    expect(dohaApi.selectProjectComposition).toHaveBeenCalledTimes(1);
    expect(dohaApi.selectProjectComposition).toHaveBeenCalledWith("project-1", "snapshot-1");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("mutation 처리 중 selector와 적용 버튼을 비활성화한다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(selectionRequired);
    let finish!: () => void;
    vi.spyOn(dohaApi, "selectProjectComposition").mockImplementation(
      () => new Promise((resolve) => {
        finish = () => resolve({ project_id: "project-1", selected_snapshot_id: "snapshot-1" });
      }),
    );
    const user = userEvent.setup();
    renderComposition();
    await user.click(await screen.findByRole("radio", { name: /Snapshot v7/ }));
    await user.click(screen.getByRole("button", { name: "선택 적용" }));
    expect(screen.getByRole("button", { name: "적용 중…" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Snapshot v7/ })).toBeDisabled();
    finish();
  });

  it("ready에서 exact AssetVersion, 안전한 Artifact metadata, Mix와 lineage를 렌더한다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(ready);
    renderComposition();
    expect(await screen.findByText("asset-version-exact")).toBeVisible();
    expect(screen.getByText("asset-version-parent")).toBeVisible();
    expect(screen.getByText("audio/wav")).toBeVisible();
    expect(screen.getByRole("link", { name: "미리보기" })).toHaveAttribute(
      "href",
      "/backend/api/v1/artifacts/artifact-1/content",
    );
    expect(screen.getByText(/master_gain_db/)).toBeVisible();
    expect(screen.getByText(/music: 1.2.0/)).toBeVisible();
    expect(screen.getByText("Section 정보 없음")).toBeVisible();
    expect(screen.queryByText(/storage key/i)).not.toBeInTheDocument();
  });

  it("refresh 또는 재진입 시 Frontend memory 없이 backend ready를 다시 읽는다", async () => {
    const get = vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(ready);
    const first = renderComposition();
    await screen.findByText("현재 선택");
    first.unmount();
    renderComposition();
    await screen.findByText("현재 선택");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("invalid selection 오류를 안전한 사용자 메시지로 표시한다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockResolvedValue(selectionRequired);
    vi.spyOn(dohaApi, "selectProjectComposition").mockRejectedValue(
      new ApiError(404, "COMPOSITION_SNAPSHOT_NOT_FOUND", "raw backend detail"),
    );
    const user = userEvent.setup();
    renderComposition();
    await user.click(await screen.findByRole("radio", { name: /Snapshot v7/ }));
    await user.click(screen.getByRole("button", { name: "선택 적용" }));
    expect(await screen.findByText("선택한 Snapshot을 찾을 수 없습니다. 목록을 새로 확인해 주세요.")).toBeVisible();
    expect(screen.queryByText("raw backend detail")).not.toBeInTheDocument();
  });

  it("API unavailable과 Project 404를 각각 안전하게 표시한다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockRejectedValue(
      new ApiError(0, "NETWORK_ERROR", "internal network detail"),
    );
    const first = renderComposition();
    expect(await screen.findByText("음악 생성 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.")).toBeVisible();
    expect(screen.queryByText("internal network detail")).not.toBeInTheDocument();
    first.unmount();

    vi.mocked(dohaApi.getProjectComposition).mockRejectedValue(
      new ApiError(404, "PROJECT_NOT_FOUND", "owner detail"),
    );
    renderComposition();
    expect(await screen.findByText("Project를 찾을 수 없거나 접근 권한이 없습니다.")).toBeVisible();
  });

  it("unauthenticated 응답을 로그인 안내로 표시한다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockRejectedValue(
      new ApiError(401, "UNAUTHENTICATED", "token detail"),
    );
    renderComposition();
    expect(await screen.findByText("로그인이 필요합니다. 다시 로그인해 주세요.")).toBeVisible();
    expect(screen.queryByText("token detail")).not.toBeInTheDocument();
  });

  it("예상하지 못한 Backend 오류의 raw message를 노출하지 않는다", async () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockRejectedValue(
      new ApiError(500, "UNEXPECTED_INTERNAL_CODE", "stack and storage detail"),
    );
    renderComposition();
    expect(await screen.findByText("Composition 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.")).toBeVisible();
    expect(screen.queryByText("stack and storage detail")).not.toBeInTheDocument();
  });

  it("aggregate 응답 전 접근 가능한 loading 상태를 표시한다", () => {
    vi.spyOn(dohaApi, "getProjectComposition").mockImplementation(() => new Promise(() => undefined));
    renderComposition();
    expect(screen.getByRole("status", { name: "Composition을 불러오는 중" })).toBeVisible();
  });

  it("기존 Studio 생성 workflow를 그대로 렌더한다", () => {
    useStudioStore.getState().reset();
    render(<StudioWorkspace />);
    expect(screen.getByText("어떤 음악을 만들까요?")).toBeVisible();
    expect(screen.queryByText("COMPOSITION WORKSPACE")).not.toBeInTheDocument();
  });
});
