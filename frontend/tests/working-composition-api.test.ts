import { afterEach, describe, expect, it, vi } from "vitest";
import { dohaApi } from "@/services/doha-api";

afterEach(() => vi.unstubAllGlobals());

describe("WorkingComposition API client", () => {
  it("exact AssetVersion media-source resolver가 공식 Project path와 abort signal을 사용한다", async () => {
    const fetchMock = mockResponses(mediaSource());
    const controller = new AbortController();
    await expect(dohaApi.resolveAssetVersionMediaSource("project/1", "version/1", controller.signal))
      .resolves.toMatchObject({ asset_version_id: "version/1", artifact_id: "artifact-1" });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/backend/api/v1/projects/project%2F1/asset-versions/version%2F1/media-source",
    );
    expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });

  it("GET과 initialize가 v1 path, explicit body, Idempotency-Key를 사용한다", async () => {
    const fetchMock = mockResponses(working(), initialize());
    await dohaApi.getWorkingComposition("project/1");
    await dohaApi.initializeWorkingComposition("project/1", "init-key");
    expect(fetchMock.mock.calls[0][0]).toBe("/backend/api/v1/projects/project%2F1/working-composition");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", body: "{}" });
    expect(headersAt(fetchMock, 1).get("Idempotency-Key")).toBe("init-key");
  });

  it("Track mutations가 expected_revision과 필요한 idempotency header를 전달한다", async () => {
    const fetchMock = mockResponses(trackResult(), trackResult(), reorderResult(), trackResult(), trackResult());
    const base = { working_composition_id: "working-1", expected_revision: 7 };
    await dohaApi.createWorkingTrack("project-1", { ...base, name: "Vocal" }, "create-key");
    await dohaApi.renameWorkingTrack("project-1", "track-1", { ...base, name: "Lead" });
    await dohaApi.reorderWorkingTracks("project-1", { ...base, ordered_track_ids: ["track-2", "track-1"] });
    await dohaApi.deleteWorkingTrack("project-1", "track-1", base, "delete-key");
    await dohaApi.restoreWorkingTrack("project-1", "track-1", { ...base, target_track_order: 1 }, "restore-key");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ expected_revision: 7, name: "Vocal" });
    expect(headersAt(fetchMock, 0).get("Idempotency-Key")).toBe("create-key");
    expect(headersAt(fetchMock, 1).has("Idempotency-Key")).toBe(false);
    expect(JSON.parse(fetchMock.mock.calls[2][1].body).ordered_track_ids).toEqual(["track-2", "track-1"]);
    expect(headersAt(fetchMock, 3).get("Idempotency-Key")).toBe("delete-key");
    expect(JSON.parse(fetchMock.mock.calls[4][1].body).target_track_order).toBe(1);
  });

  it("Clip create/move/trim/delete/restore가 canonical fields와 revision을 그대로 전달한다", async () => {
    const fetchMock = mockResponses(...Array.from({ length: 7 }, clipResult));
    const base = { working_composition_id: "working-1", expected_revision: 4 };
    await dohaApi.createWorkingClip("project-1", { ...base, track_id: "track-1", source_asset_version_id: "version-1", timeline_start: "1.000", source_in: "0.000", source_out: "9.000" }, "create-key");
    await dohaApi.moveWorkingClip("project-1", "clip-1", { ...base, timeline_start: "2.000" });
    await dohaApi.trimWorkingClipStart("project-1", "clip-1", { ...base, timeline_start: "3.000", source_in: "1.000" });
    await dohaApi.trimWorkingClipEnd("project-1", "clip-1", { ...base, source_out: "8.000" });
    await dohaApi.deleteWorkingClip("project-1", "clip-1", base, "delete-key");
    await dohaApi.restoreWorkingClip("project-1", "clip-1", base, "restore-key");
    await dohaApi.splitWorkingClip("project-1", "clip-1", { ...base, split_at: "4.000" }, "split-key");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ source_asset_version_id: "version-1", expected_revision: 4 });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toMatchObject({ timeline_start: "3.000", source_in: "1.000" });
    expect(headersAt(fetchMock, 4).get("Idempotency-Key")).toBe("delete-key");
    expect(headersAt(fetchMock, 5).get("Idempotency-Key")).toBe("restore-key");
    expect(headersAt(fetchMock, 6).get("Idempotency-Key")).toBe("split-key");
  });

  it("checkout/unsplit/resplit이 history identity와 새 key를 전달한다", async () => {
    const fetchMock = mockResponses(checkout(), split(), split());
    const base = { working_composition_id: "working-1", expected_revision: 10 };
    await dohaApi.checkoutWorkingComposition("project-1", { ...base, composition_snapshot_id: "snapshot-1" }, "checkout-key");
    const children = { ...base, left_clip_id: "left", right_clip_id: "right" };
    await dohaApi.unsplitWorkingClip("project-1", "original", children, "undo-key");
    await dohaApi.resplitWorkingClip("project-1", "original", children, "redo-key");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).composition_snapshot_id).toBe("snapshot-1");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ left_clip_id: "left", right_clip_id: "right", expected_revision: 10 });
    expect(headersAt(fetchMock, 1).get("Idempotency-Key")).toBe("undo-key");
    expect(headersAt(fetchMock, 2).get("Idempotency-Key")).toBe("redo-key");
  });
});

function mockResponses(...data: object[]) {
  const mock = vi.fn();
  data.forEach((item) => mock.mockResolvedValueOnce(new Response(JSON.stringify({ data: item }), { status: 200 })));
  vi.stubGlobal("fetch", mock);
  return mock;
}
function headersAt(mock: ReturnType<typeof vi.fn>, index: number): Headers { return mock.mock.calls[index][1].headers as Headers; }
function working() { return { working_composition_id: "working-1", project_id: "project-1", base_composition_snapshot_id: null, revision: 0, mix_settings: {}, tracks: [], clips: [], timeline_duration: "0" }; }
function initialize() { return { working_composition_id: "working-1", completed_revision: 0, replayed: false }; }
function trackResult() { return { track_id: "track-1", completed_revision: 8, replayed: false }; }
function reorderResult() { return { working_composition_id: "working-1", completed_revision: 8 }; }
function clipResult() { return { clip_id: "clip-1", completed_revision: 5, replayed: false }; }
function split() { return { original_clip_id: "original", left_clip_id: "left", right_clip_id: "right", completed_revision: 11, replayed: false }; }
function checkout() { return { working_composition_id: "working-1", base_composition_snapshot_id: "snapshot-1", completed_revision: 11, replayed: false }; }
function mediaSource() { return { asset_version_id: "version/1", artifact_id: "artifact-1", media_type: "audio/wav", size_bytes: 48, artifact_checksum: "a".repeat(64), duration_seconds: "10", content_url: "/api/v1/artifacts/artifact-1/content" }; }
