import { useEffect, useMemo, useRef, useState } from "react";
import { dohaApi, toBackendPublicUrl } from "@/services/doha-api";
import type { AssetVersionMediaSourceDto } from "@/types/api";
import {
  loadWaveformPeaks,
  MAX_WAVEFORM_PEAKS,
  type WaveformLoader,
} from "./waveform";

export const MAX_WORKING_WAVEFORM_CACHE_ENTRIES = 64;

export interface CanonicalWorkingWaveform {
  assetVersionId: string;
  sourceKey: string;
  durationSeconds: number;
  peaks: number[];
}

export type WorkingWaveformState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; waveform: CanonicalWorkingWaveform };

export type MediaSourceResolver = (
  projectId: string,
  assetVersionId: string,
  signal: AbortSignal,
) => Promise<AssetVersionMediaSourceDto>;

interface CacheEntry {
  controller: AbortController;
  promise: Promise<CanonicalWorkingWaveform>;
  settled: boolean;
  wasAborted: boolean;
  lastUsed: number;
}

export class WorkingWaveformSession {
  private readonly entries = new Map<string, CacheEntry>();
  private disposed = false;
  private clock = 0;

  constructor(
    private readonly projectId: string,
    private readonly resolver: MediaSourceResolver = dohaApi.resolveAssetVersionMediaSource,
    private readonly loader: WaveformLoader = loadWaveformPeaks,
    private readonly sessionIdentity = "",
  ) {}

  load(assetVersionId: string): Promise<CanonicalWorkingWaveform> {
    const existing = this.entries.get(assetVersionId);
    if (existing) {
      if (existing.settled && !existing.wasAborted) {
        existing.lastUsed = ++this.clock;
        return existing.promise;
      }
      if (!existing.settled && !existing.controller.signal.aborted) {
        existing.lastUsed = ++this.clock;
        return existing.promise;
      }
      this.entries.delete(assetVersionId);
    }
    if (this.disposed) return Promise.reject(abortError());
    this.evictForCapacity();
    if (this.entries.size >= MAX_WORKING_WAVEFORM_CACHE_ENTRIES) {
      return Promise.reject(new Error("WORKING_WAVEFORM_CACHE_CAPACITY"));
    }

    const controller = new AbortController();
    const entry: CacheEntry = {
      controller,
      settled: false,
      wasAborted: false,
      lastUsed: ++this.clock,
      promise: Promise.resolve(undefined as never),
    };
    entry.promise = this.resolveAndDecode(assetVersionId, controller.signal)
      .catch((error) => {
        if (isAbortError(error) || this.disposed || controller.signal.aborted) entry.wasAborted = true;
        throw error;
      })
      .finally(() => { entry.settled = true; });
    this.entries.set(assetVersionId, entry);
    return entry.promise;
  }

  invalidate(assetVersionId: string): void {
    const entry = this.entries.get(assetVersionId);
    entry?.controller.abort();
    this.entries.delete(assetVersionId);
  }

  dispose(): void {
    this.disposed = true;
    for (const entry of this.entries.values()) entry.controller.abort();
    this.entries.clear();
  }

  activate(): void {
    this.disposed = false;
  }

  private evictForCapacity(): void {
    if (this.entries.size < MAX_WORKING_WAVEFORM_CACHE_ENTRIES) return;
    const candidate = [...this.entries.entries()]
      .filter(([, entry]) => entry.settled)
      .sort((left, right) => left[1].lastUsed - right[1].lastUsed)[0];
    if (!candidate) return;
    candidate[1].controller.abort();
    this.entries.delete(candidate[0]);
  }

  private async resolveAndDecode(
    assetVersionId: string,
    signal: AbortSignal,
  ): Promise<CanonicalWorkingWaveform> {
    try {
      const source = await this.resolver(this.projectId, assetVersionId, signal);
      if (signal.aborted || this.disposed) throw abortError();
      const contentUrl = toBackendPublicUrl(source.content_url);
      const durationSeconds = Number(source.duration_seconds);
      if (
        source.asset_version_id !== assetVersionId
        || !contentUrl
        || !Number.isFinite(durationSeconds)
        || durationSeconds <= 0
      ) {
        throw new Error("WORKING_WAVEFORM_SOURCE_INVALID");
      }
      const sourceKey = [
        this.projectId,
        this.sessionIdentity,
        assetVersionId,
        source.artifact_id,
        source.artifact_checksum,
      ].join(":");
      const peaks = await this.loader({
        cacheKey: sourceKey,
        contentUrl,
        mediaType: source.media_type,
        sizeBytes: source.size_bytes,
      }, signal);
      if (signal.aborted || this.disposed) throw abortError();
      if (!peaks.length) throw new Error("WORKING_WAVEFORM_EMPTY");
      return {
        assetVersionId,
        sourceKey,
        durationSeconds,
        peaks: peaks.slice(0, MAX_WAVEFORM_PEAKS),
      };
    } catch (error) {
      if (signal.aborted || this.disposed) throw abortError();
      throw error;
    }
  }
}

export function useWorkingWaveforms({
  projectId,
  workingCompositionId,
  assetVersionIds,
  resolver,
  loader,
}: {
  projectId: string;
  workingCompositionId: string;
  assetVersionIds: string[];
  resolver?: MediaSourceResolver;
  loader?: WaveformLoader;
}): (assetVersionId: string) => WorkingWaveformState {
  const session = useMemo(
    () => new WorkingWaveformSession(projectId, resolver, loader, workingCompositionId),
    [loader, projectId, resolver, workingCompositionId],
  );
  const requestIdRef = useRef(0);
  const [loaded, setLoaded] = useState<{
    session: WorkingWaveformSession;
    states: Map<string, WorkingWaveformState>;
  }>(() => ({ session, states: new Map() }));
  const assetVersionKey = [...new Set(assetVersionIds)].sort().join("\u0000");
  const uniqueIds = useMemo(
    () => assetVersionKey ? assetVersionKey.split("\u0000") : [],
    [assetVersionKey],
  );

  useEffect(() => {
    session.activate();
    return () => session.dispose();
  }, [session]);

  useEffect(() => {
    let active = true;
    const requestId = ++requestIdRef.current;
    for (const assetVersionId of uniqueIds) {
      void session.load(assetVersionId).then((waveform) => {
        if (!active || requestIdRef.current !== requestId) return;
        setLoaded((current) => {
          const states = current.session === session ? new Map(current.states) : new Map();
          states.set(assetVersionId, { status: "ready", waveform });
          return { session, states };
        });
      }).catch((error: unknown) => {
        if (!active || requestIdRef.current !== requestId || isAbortError(error)) return;
        setLoaded((current) => {
          const states = current.session === session ? new Map(current.states) : new Map();
          states.set(assetVersionId, { status: "unavailable" });
          return { session, states };
        });
      });
    }
    return () => {
      active = false;
    };
  }, [session, uniqueIds]);

  return (assetVersionId) => (
    loaded.session === session
      ? loaded.states.get(assetVersionId) ?? { status: "loading" }
      : { status: "loading" }
  );
}

export function projectWaveformWindow(
  waveform: CanonicalWorkingWaveform,
  sourceIn: number,
  sourceOut: number,
  peakLimit = MAX_WAVEFORM_PEAKS,
  sourceDuration = waveform.durationSeconds,
): number[] {
  const duration = sourceDuration;
  if (
    !Number.isFinite(sourceIn)
    || !Number.isFinite(sourceOut)
    || sourceOut <= sourceIn
    || duration <= 0
    || !waveform.peaks.length
  ) return [];
  const start = Math.max(0, Math.min(sourceIn, duration));
  const end = Math.max(start, Math.min(sourceOut, duration));
  if (end <= start) return [];

  const sourcePeakCount = waveform.peaks.length;
  const boundedLimit = Math.min(Math.max(Math.floor(peakLimit), 1), MAX_WAVEFORM_PEAKS);
  const projectedCount = Math.min(
    boundedLimit,
    Math.max(1, Math.ceil(((end - start) / duration) * sourcePeakCount)),
  );
  const projected = new Array<number>(projectedCount).fill(0);
  for (let index = 0; index < projectedCount; index += 1) {
    const bucketStart = start + ((end - start) * index) / projectedCount;
    const bucketEnd = start + ((end - start) * (index + 1)) / projectedCount;
    const firstSourceIndex = Math.min(
      sourcePeakCount - 1,
      Math.floor((bucketStart / duration) * sourcePeakCount),
    );
    const lastSourceExclusive = Math.min(
      sourcePeakCount,
      Math.max(firstSourceIndex + 1, Math.ceil((bucketEnd / duration) * sourcePeakCount)),
    );
    let peak = 0;
    for (let sourceIndex = firstSourceIndex; sourceIndex < lastSourceExclusive; sourceIndex += 1) {
      const candidate = waveform.peaks[sourceIndex] ?? 0;
      if (Number.isFinite(candidate)) peak = Math.max(peak, candidate);
    }
    projected[index] = peak;
  }
  return projected;
}

export function waveformProjectionSignature(peaks: number[]): string {
  let hash = 2166136261;
  for (const peak of peaks) {
    hash ^= Math.round(Math.max(0, Math.min(1, peak)) * 10_000);
    hash = Math.imul(hash, 16777619);
  }
  return `${peaks.length}:${(hash >>> 0).toString(16)}`;
}

function isAbortError(error: unknown): boolean {
  const message = typeof error === "object" && error !== null
    ? String((error as { message?: unknown }).message ?? "")
    : "";
  return !!(
    (error instanceof DOMException && error.name === "AbortError")
    || (error instanceof Error && error.name === "AbortError")
    || (error instanceof Error && (error as Error & { code?: unknown }).code === "ERR_ABORTED")
    || (typeof error === "object" && error !== null && (error as { name?: unknown }).name === "AbortError")
    || (typeof error === "object" && error !== null && (error as { code?: unknown }).code === "ERR_ABORTED")
    || (typeof error === "object" && error !== null && (error as { name?: unknown }).name === "TypeError" && message.includes("abort"))
    || (typeof error === "object" && error !== null && (error as { code?: unknown }).code === "DOMException" && message.includes("abort"))
    || message.toLowerCase().includes("abort")
  );
}

function abortError(): DOMException {
  return new DOMException("Aborted", "AbortError");
}
