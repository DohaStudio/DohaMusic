"use client";

import { Pause, Play, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import { usePlayerStore } from "@/stores/player-store";
import type { CompositionTrackProjectionDto } from "@/types/api";
import type { CompositionPlaybackResolution } from "./timeline-playback";
import {
  clampTimelineTime,
  formatTimelinePreciseTime,
  formatTimelineTime,
  timelineTimeToPixels,
  timelineTimeFromPointer,
} from "./timeline-playback";
import {
  buildWaveformPath,
  loadWaveformPeaks,
  type WaveformLoader,
} from "./waveform";

const MIN_PIXELS_PER_SECOND = 32;
const MAX_PIXELS_PER_SECOND = 128;
const DEFAULT_PIXELS_PER_SECOND = 64;
const EMPTY_TIMELINE_WIDTH = 720;
const TRACK_LABEL_WIDTH = 164;

export function CompositionTimeline({
  tracks,
  playback,
  waveformLoader = loadWaveformPeaks,
}: {
  tracks: CompositionTrackProjectionDto[];
  playback: CompositionPlaybackResolution;
  waveformLoader?: WaveformLoader;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const waveformRequestRef = useRef(0);
  const dragPointerRef = useRef<number | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(DEFAULT_PIXELS_PER_SECOND);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(tracks[0]?.projection_id ?? null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [dragPreviewTime, setDragPreviewTime] = useState<number | null>(null);
  const [loadedWaveform, setLoadedWaveform] = useState<LoadedWaveformState | null>(null);
  const currentFile = usePlayerStore((state) => state.currentFile);
  const shouldPlay = usePlayerStore((state) => state.shouldPlay);
  const playerTime = usePlayerStore((state) => state.currentTime);
  const playerDuration = usePlayerStore((state) => state.duration);
  const loading = usePlayerStore((state) => state.loading);
  const error = usePlayerStore((state) => state.error);
  const select = usePlayerStore((state) => state.select);
  const play = usePlayerStore((state) => state.play);
  const pause = usePlayerStore((state) => state.pause);
  const seek = usePlayerStore((state) => state.seek);
  const source = playback.status === "available" ? playback.source : undefined;
  const waveformSource = playback.status === "available" ? playback.waveformSource : undefined;
  const waveformCacheKey = waveformSource?.cacheKey;
  const waveformContentUrl = waveformSource?.contentUrl;
  const waveformMediaType = waveformSource?.mediaType;
  const waveformSizeBytes = waveformSource?.sizeBytes;
  const waveform: WaveformState = !waveformSource
    ? { status: "unavailable" }
    : loadedWaveform?.sourceKey === waveformSource.cacheKey
      ? loadedWaveform
      : { status: "loading" };
  const effectiveSelectedTrackId = tracks.some((track) => track.projection_id === selectedTrackId)
    ? selectedTrackId
    : (tracks[0]?.projection_id ?? null);
  const isActiveSource = Boolean(source && currentFile?.id === source.id);
  const currentTime = isActiveSource ? playerTime : 0;
  const duration = isActiveSource ? playerDuration : 0;
  const displayedTime = dragPreviewTime ?? currentTime;
  const timelineWidth = duration > 0
    ? TRACK_LABEL_WIDTH + Math.max(duration * pixelsPerSecond, EMPTY_TIMELINE_WIDTH)
    : TRACK_LABEL_WIDTH + EMPTY_TIMELINE_WIDTH;

  useEffect(() => {
    if (source) select(source);
  }, [select, source]);

  useEffect(() => {
    const requestId = waveformRequestRef.current + 1;
    waveformRequestRef.current = requestId;
    if (
      !waveformCacheKey
      || !waveformContentUrl
      || !waveformMediaType
      || waveformSizeBytes === undefined
    ) return;

    const controller = new AbortController();
    void waveformLoader({
      cacheKey: waveformCacheKey,
      contentUrl: waveformContentUrl,
      mediaType: waveformMediaType,
      sizeBytes: waveformSizeBytes,
    }, controller.signal).then((peaks) => {
      if (controller.signal.aborted || waveformRequestRef.current !== requestId) return;
      setLoadedWaveform(peaks.length
        ? { sourceKey: waveformCacheKey, status: "ready", peaks }
        : { sourceKey: waveformCacheKey, status: "failed" });
    }).catch((error: unknown) => {
      if (
        controller.signal.aborted
        || waveformRequestRef.current !== requestId
        || (error instanceof DOMException && error.name === "AbortError")
      ) return;
      setLoadedWaveform({ sourceKey: waveformCacheKey, status: "failed" });
    });
    return () => {
      controller.abort();
    };
  }, [
    waveformCacheKey,
    waveformContentUrl,
    waveformLoader,
    waveformMediaType,
    waveformSizeBytes,
  ]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!source || isEditableTarget(event.target)) return;
      if (event.code === "Space") {
        event.preventDefault();
        if (shouldPlay && isActiveSource) pause();
        else play(source);
      }
      if ((event.code === "ArrowLeft" || event.code === "ArrowRight") && duration > 0) {
        event.preventDefault();
        const delta = event.code === "ArrowLeft" ? -5 : 5;
        seek(clampTimelineTime(currentTime + delta, duration));
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentTime, duration, isActiveSource, pause, play, seek, shouldPlay, source]);

  const ticks = useMemo(
    () => buildTicks(duration, pixelsPerSecond),
    [duration, pixelsPerSecond],
  );

  function timeFromPointer(clientX: number) {
    const viewport = viewportRef.current;
    if (!viewport || !source || duration <= 0) return null;
    return timelineTimeFromPointer({
      clientX: clientX - TRACK_LABEL_WIDTH,
      viewportLeft: viewport.getBoundingClientRect().left,
      scrollLeft: viewport.scrollLeft,
      pixelsPerSecond,
      duration,
    });
  }

  function seekFromPointer(clientX: number) {
    const next = timeFromPointer(clientX);
    if (next === null) return;
    seek(next);
  }

  function previewFromPointer(clientX: number) {
    const next = timeFromPointer(clientX);
    if (next !== null && dragPointerRef.current === null) setHoverTime(next);
  }

  function startPlayheadDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const next = timeFromPointer(event.clientX);
    if (next === null) return;
    event.preventDefault();
    dragPointerRef.current = event.pointerId;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setHoverTime(null);
    setDragPreviewTime(next);
  }

  function movePlayheadDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragPointerRef.current !== event.pointerId) return;
    const next = timeFromPointer(event.clientX);
    if (next !== null) setDragPreviewTime(next);
  }

  function finishPlayheadDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragPointerRef.current !== event.pointerId) return;
    const next = timeFromPointer(event.clientX);
    dragPointerRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    setDragPreviewTime(null);
    if (next !== null) seek(next);
  }

  function cancelPlayheadDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragPointerRef.current !== event.pointerId) return;
    dragPointerRef.current = null;
    setDragPreviewTime(null);
  }

  function onPlayheadKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!source || duration <= 0) return;
    let next: number | null = null;
    if (event.key === "ArrowLeft") next = currentTime - 1;
    if (event.key === "ArrowRight") next = currentTime + 1;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = duration;
    if (next === null) return;
    event.preventDefault();
    event.stopPropagation();
    seek(clampTimelineTime(next, duration));
  }

  return (
    <section className="composition-timeline" aria-labelledby="timeline-title">
      <header className="timeline-heading">
        <div>
          <p className="eyebrow">TIMELINE PLAYBACK FOUNDATION</p>
          <h4 id="timeline-title">Composition Timeline</h4>
        </div>
        <div className="timeline-zoom" aria-label="Timeline 확대/축소">
          <button
            type="button"
            aria-label="Timeline 축소"
            disabled={pixelsPerSecond === MIN_PIXELS_PER_SECOND}
            onClick={() => setPixelsPerSecond((value) => Math.max(MIN_PIXELS_PER_SECOND, value - 16))}
          >
            <ZoomOut aria-hidden="true" />
          </button>
          <output aria-label="Timeline 배율">{pixelsPerSecond}px/s</output>
          <button
            type="button"
            aria-label="Timeline 확대"
            disabled={pixelsPerSecond === MAX_PIXELS_PER_SECOND}
            onClick={() => setPixelsPerSecond((value) => Math.min(MAX_PIXELS_PER_SECOND, value + 16))}
          >
            <ZoomIn aria-hidden="true" />
          </button>
        </div>
      </header>

      {playback.status === "unavailable" && (
        <div className="timeline-unavailable" role="status">
          <strong>{playback.code}</strong>
          <span>{playback.reason} Timeline과 Track은 표시하지만 재생은 비활성화합니다.</span>
        </div>
      )}
      {playback.status === "available" && loading && (
        <p className="timeline-media-state" role="status">Audio metadata를 불러오는 중입니다.</p>
      )}
      {playback.status === "available" && error && (
        <p className="timeline-media-state error" role="alert">{error}</p>
      )}

      <div className="timeline-scroll" ref={viewportRef} data-testid="timeline-scroll">
        <div className="timeline-canvas" style={{ width: timelineWidth }}>
          <button
            type="button"
            className="timeline-ruler"
            aria-label="초 단위 Timeline ruler"
            disabled={!source || duration <= 0}
            onClick={(event) => seekFromPointer(event.clientX)}
            onPointerMove={(event) => previewFromPointer(event.clientX)}
            onPointerLeave={() => setHoverTime(null)}
          >
            {ticks.map((tick) => (
              <span key={tick} style={{ left: TRACK_LABEL_WIDTH + tick * pixelsPerSecond }}>
                {formatTimelineTime(tick)}
              </span>
            ))}
          </button>
          <div className="timeline-waveform-row">
            <div className="timeline-waveform-label">
              <strong>Master / Mix</strong>
              <span>재생 Overview</span>
            </div>
            <button
              type="button"
              className="timeline-waveform-surface"
              aria-label="Master Mix Waveform에서 재생 위치 선택"
              disabled={!source || duration <= 0}
              onClick={(event) => seekFromPointer(event.clientX)}
              onPointerMove={(event) => previewFromPointer(event.clientX)}
              onPointerLeave={() => setHoverTime(null)}
            >
              {waveform.status === "loading" && <span role="status">Waveform을 불러오는 중입니다.</span>}
              {waveform.status === "unavailable" && <span>Waveform source를 사용할 수 없습니다.</span>}
              {waveform.status === "failed" && <span role="status">Waveform을 표시할 수 없습니다. 재생은 계속 사용할 수 있습니다.</span>}
              {waveform.status === "ready" && (
                <svg
                  aria-hidden="true"
                  data-testid="master-waveform"
                  data-peak-count={waveform.peaks.length}
                  viewBox="0 0 1000 96"
                  preserveAspectRatio="none"
                >
                  <path d={buildWaveformPath(waveform.peaks)} />
                </svg>
              )}
            </button>
          </div>
          <div className="timeline-track-lanes" role="list" aria-label="Composition Track lanes">
            {tracks.map((track) => {
              const selected = effectiveSelectedTrackId === track.projection_id;
              return (
                <article
                  className={`timeline-track-lane${selected ? " selected" : ""}`}
                  key={track.projection_id}
                  role="listitem"
                >
                  <button
                    type="button"
                    className="timeline-track-label"
                    aria-label={trackLabel(track.item_role, track.sort_order)}
                    aria-pressed={selected}
                    onClick={() => setSelectedTrackId(track.projection_id)}
                  >
                    <strong>{trackLabel(track.item_role, track.sort_order)}</strong>
                    <span>{track.item_role} · snapshot-local</span>
                  </button>
                  <button
                    type="button"
                    className="timeline-lane-surface"
                    aria-label={`${trackLabel(track.item_role, track.sort_order)}에서 재생 위치 선택`}
                    disabled={!source || duration <= 0}
                    onClick={(event) => seekFromPointer(event.clientX)}
                  >
                    <span>Clip 없음 · Track projection</span>
                  </button>
                </article>
              );
            })}
          </div>
          <div
            className="timeline-playhead"
            style={{ left: TRACK_LABEL_WIDTH + timelineTimeToPixels(displayedTime, pixelsPerSecond) }}
            aria-hidden="true"
          />
          {source && duration > 0 && (
            <div
              className="timeline-playhead-handle"
              role="slider"
              tabIndex={0}
              aria-label="Timeline Playhead 재생 위치"
              aria-valuemin={0}
              aria-valuemax={duration}
              aria-valuenow={displayedTime}
              aria-valuetext={formatTimelinePreciseTime(displayedTime)}
              style={{ left: TRACK_LABEL_WIDTH + timelineTimeToPixels(displayedTime, pixelsPerSecond) }}
              onPointerDown={startPlayheadDrag}
              onPointerMove={movePlayheadDrag}
              onPointerUp={finishPlayheadDrag}
              onPointerCancel={cancelPlayheadDrag}
              onKeyDown={onPlayheadKeyDown}
            />
          )}
          {hoverTime !== null && dragPreviewTime === null && source && duration > 0 && (
            <output
              className="timeline-time-preview"
              aria-label="Seek 미리보기 시간"
              style={{ left: TRACK_LABEL_WIDTH + timelineTimeToPixels(hoverTime, pixelsPerSecond) }}
            >
              {formatTimelinePreciseTime(hoverTime)}
            </output>
          )}
        </div>
      </div>

      <footer className="timeline-transport" aria-label="Timeline transport">
        <button
          type="button"
          className="timeline-play-button"
          disabled={!source}
          aria-label={shouldPlay && isActiveSource ? "Timeline 일시정지" : "Timeline 재생"}
          onClick={() => {
            if (!source) return;
            if (shouldPlay && isActiveSource) pause();
            else play(source);
          }}
        >
          {shouldPlay && isActiveSource ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
        </button>
        <button
          type="button"
          disabled={!source || duration <= 0}
          aria-label="5초 뒤로"
          onClick={() => seek(clampTimelineTime(currentTime - 5, duration))}
        >
          −5s
        </button>
        <time aria-label="현재 재생 시간과 전체 길이">
          {formatTimelinePreciseTime(displayedTime)} / {duration > 0 ? formatTimelineTime(duration) : "길이 확인 전"}
        </time>
        <button
          type="button"
          disabled={!source || duration <= 0}
          aria-label="5초 앞으로"
          onClick={() => seek(clampTimelineTime(currentTime + 5, duration))}
        >
          +5s
        </button>
        <span>Space 재생/일시정지 · ←/→ 5초 이동</span>
      </footer>
    </section>
  );
}

type WaveformState =
  | { status: "unavailable" | "loading" | "failed" }
  | { status: "ready"; peaks: number[] };

type LoadedWaveformState =
  | { sourceKey: string; status: "failed" }
  | { sourceKey: string; status: "ready"; peaks: number[] };

function buildTicks(duration: number, pixelsPerSecond: number): number[] {
  if (duration <= 0) return [0];
  const step = pixelsPerSecond >= 96 ? 5 : pixelsPerSecond >= 48 ? 10 : 30;
  const ticks: number[] = [];
  for (let time = 0; time <= duration; time += step) ticks.push(time);
  if (ticks.at(-1) !== duration) ticks.push(duration);
  return ticks;
}

function trackLabel(role: CompositionTrackProjectionDto["item_role"], sortOrder: number): string {
  return `${role[0].toUpperCase()}${role.slice(1)} ${sortOrder + 1}`;
}

function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (
    target.isContentEditable
    || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
}
