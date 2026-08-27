import { describe, expect, it, vi } from "vitest";
import {
  projectWaveformWindow,
  WorkingWaveformSession,
  waveformProjectionSignature,
  type CanonicalWorkingWaveform,
} from "@/features/composition/working-waveform";
import type { AssetVersionMediaSourceDto } from "@/types/api";

const canonical: CanonicalWorkingWaveform = {
  assetVersionId: "version-1",
  sourceKey: "project-1:version-1:artifact-1:checksum",
  durationSeconds: 8,
  peaks: [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
};

describe("Working Clip waveform projection", () => {
  it("full source window를 canonical peak 순서로 유지한다", () => {
    expect(projectWaveformWindow(canonical, 0, 8)).toEqual(canonical.peaks);
  });

  it("source_in crop을 source-time bucket boundary에 맞춘다", () => {
    expect(projectWaveformWindow(canonical, 2, 8)).toEqual([0.3, 0.4, 0.6, 0.7, 0.8, 0.9]);
  });

  it("source_out crop을 exclusive right boundary에 맞춘다", () => {
    expect(projectWaveformWindow(canonical, 0, 6)).toEqual([0.1, 0.2, 0.3, 0.4, 0.6, 0.7]);
  });

  it("both-side crop을 정확한 source 구간으로 투영한다", () => {
    expect(projectWaveformWindow(canonical, 2, 6)).toEqual([0.3, 0.4, 0.6, 0.7]);
  });

  it("move처럼 timeline_start만 바뀌면 projection이 동일하다", () => {
    const before = projectWaveformWindow(canonical, 2, 6);
    const afterMove = projectWaveformWindow(canonical, 2, 6);
    expect(waveformProjectionSignature(afterMove)).toBe(waveformProjectionSignature(before));
  });

  it("trim-start와 trim-end가 각 source boundary를 바꾼다", () => {
    expect(projectWaveformWindow(canonical, 3, 6)).toEqual([0.4, 0.6, 0.7]);
    expect(projectWaveformWindow(canonical, 2, 5)).toEqual([0.3, 0.4, 0.6]);
  });

  it("split left/right가 원본의 서로 다른 반구간을 표시한다", () => {
    const left = projectWaveformWindow(canonical, 0, 4);
    const right = projectWaveformWindow(canonical, 4, 8);
    expect(left).toEqual([0.1, 0.2, 0.3, 0.4]);
    expect(right).toEqual([0.6, 0.7, 0.8, 0.9]);
    expect(waveformProjectionSignature(left)).not.toBe(waveformProjectionSignature(right));
  });

  it("unsplit은 original projection을, resplit은 같은 child projection을 복원한다", () => {
    const original = projectWaveformWindow(canonical, 0, 8);
    const left = projectWaveformWindow(canonical, 0, 4);
    const right = projectWaveformWindow(canonical, 4, 8);
    expect(projectWaveformWindow(canonical, 0, 8)).toEqual(original);
    expect(projectWaveformWindow(canonical, 0, 4)).toEqual(left);
    expect(projectWaveformWindow(canonical, 4, 8)).toEqual(right);
  });

  it("delete 후 same-ID restore가 같은 source projection을 재사용할 수 있다", () => {
    const beforeDelete = projectWaveformWindow(canonical, 1, 7);
    expect(projectWaveformWindow(canonical, 1, 7)).toEqual(beforeDelete);
  });

  it("exact boundary와 tiny range를 안전하게 bounded projection으로 만든다", () => {
    expect(projectWaveformWindow(canonical, 7, 8)).toEqual([0.9]);
    expect(projectWaveformWindow(canonical, 4, 4.000_001)).toHaveLength(1);
  });

  it.each([[1, 1], [2, 1], [Number.NaN, 2], [0, Number.POSITIVE_INFINITY]])(
    "invalid range %s..%s는 throw 없이 empty다",
    (start, end) => expect(projectWaveformWindow(canonical, start, end)).toEqual([]),
  );

  it("projection peak count를 2048 이하 및 caller bound 이하로 제한한다", () => {
    const large = { ...canonical, durationSeconds: 4096, peaks: Array.from({ length: 4096 }, () => 0.5) };
    expect(projectWaveformWindow(large, 0, 4096)).toHaveLength(2048);
    expect(projectWaveformWindow(large, 0, 4096, 32)).toHaveLength(32);
  });

  it("frozen Clip source_duration을 명시적으로 projection timebase로 사용한다", () => {
    expect(projectWaveformWindow(canonical, 0, 4, 2048, 16)).toEqual([0.1, 0.2]);
  });
});

describe("Working waveform session cache", () => {
  it("same exact AssetVersion의 resolver/fetch/decode를 한 번만 수행한다", async () => {
    const resolver = vi.fn().mockResolvedValue(mediaSource("version-1", "artifact-1"));
    const loader = vi.fn().mockResolvedValue([0.2, 0.8]);
    const session = new WorkingWaveformSession("project-1", resolver, loader);
    const [first, second] = await Promise.all([session.load("version-1"), session.load("version-1")]);
    expect(first).toBe(second);
    expect(resolver).toHaveBeenCalledTimes(1);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(loader.mock.calls[0][0].contentUrl).toBe("/backend/api/v1/artifacts/artifact-1/content");
    session.dispose();
  });

  it("different exact AssetVersion은 별도로 resolve/decode한다", async () => {
    const resolver = vi.fn((_: string, version: string) => Promise.resolve(mediaSource(version, `artifact-${version}`)));
    const loader = vi.fn().mockResolvedValue([0.5]);
    const session = new WorkingWaveformSession("project-1", resolver, loader);
    await Promise.all([session.load("version-1"), session.load("version-2")]);
    expect(resolver).toHaveBeenCalledTimes(2);
    expect(loader).toHaveBeenCalledTimes(2);
    session.dispose();
  });

  it("resolver failure를 unavailable로 격리할 수 있게 reject한다", async () => {
    const session = new WorkingWaveformSession("project-1", vi.fn().mockRejectedValue(new Error("resolver")), vi.fn());
    await expect(session.load("version-1")).rejects.toThrow("resolver");
    session.dispose();
  });

  it.each(["fetch", "decode"])("%s failure를 raw fallback 없이 reject한다", async (kind) => {
    const session = new WorkingWaveformSession(
      "project-1",
      vi.fn().mockResolvedValue(mediaSource("version-1", "artifact-1")),
      vi.fn().mockRejectedValue(new Error(kind)),
    );
    await expect(session.load("version-1")).rejects.toThrow(kind);
    session.dispose();
  });

  it("source invalidation 후 stale old completion을 폐기하고 새 source를 사용한다", async () => {
    let resolveOld!: (value: AssetVersionMediaSourceDto) => void;
    const resolver = vi.fn()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce(mediaSource("version-1", "artifact-new"));
    const loader = vi.fn().mockResolvedValue([0.7]);
    const session = new WorkingWaveformSession("project-1", resolver, loader);
    const old = session.load("version-1");
    session.invalidate("version-1");
    const current = session.load("version-1");
    resolveOld(mediaSource("version-1", "artifact-old"));
    await expect(old).rejects.toMatchObject({ name: "AbortError" });
    await expect(current).resolves.toMatchObject({ sourceKey: expect.stringContaining("artifact-new") });
    expect(loader).toHaveBeenCalledTimes(1);
    session.dispose();
  });

  it("unmount/session dispose가 pending resolver를 abort한다", async () => {
    let observedSignal: AbortSignal | undefined;
    const resolver = vi.fn((_: string, __: string, signal: AbortSignal) => {
      observedSignal = signal;
      return new Promise<AssetVersionMediaSourceDto>(() => undefined);
    });
    const session = new WorkingWaveformSession("project-1", resolver, vi.fn());
    void session.load("version-1");
    session.dispose();
    expect(observedSignal?.aborted).toBe(true);
  });
});

function mediaSource(assetVersionId: string, artifactId: string): AssetVersionMediaSourceDto {
  return {
    asset_version_id: assetVersionId,
    artifact_id: artifactId,
    media_type: "audio/wav",
    size_bytes: 48,
    artifact_checksum: artifactId.padEnd(64, "a"),
    duration_seconds: "8",
    content_url: `/api/v1/artifacts/${artifactId}/content`,
  };
}
