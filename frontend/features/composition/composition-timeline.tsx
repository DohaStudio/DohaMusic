"use client";

import { Pause, Play, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePlayerStore } from "@/stores/player-store";
import type { CompositionTrackProjectionDto } from "@/types/api";
import type { CompositionPlaybackResolution } from "./timeline-playback";
import {
  clampTimelineTime,
  formatTimelineTime,
  timelineTimeFromPointer,
} from "./timeline-playback";

const MIN_PIXELS_PER_SECOND = 32;
const MAX_PIXELS_PER_SECOND = 128;
const DEFAULT_PIXELS_PER_SECOND = 64;
const EMPTY_TIMELINE_WIDTH = 720;
const TRACK_LABEL_WIDTH = 164;

export function CompositionTimeline({
  tracks,
  playback,
}: {
  tracks: CompositionTrackProjectionDto[];
  playback: CompositionPlaybackResolution;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(DEFAULT_PIXELS_PER_SECOND);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(tracks[0]?.projection_id ?? null);
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
  const effectiveSelectedTrackId = tracks.some((track) => track.projection_id === selectedTrackId)
    ? selectedTrackId
    : (tracks[0]?.projection_id ?? null);
  const isActiveSource = Boolean(source && currentFile?.id === source.id);
  const currentTime = isActiveSource ? playerTime : 0;
  const duration = isActiveSource ? playerDuration : 0;
  const timelineWidth = duration > 0
    ? TRACK_LABEL_WIDTH + Math.max(duration * pixelsPerSecond, EMPTY_TIMELINE_WIDTH)
    : TRACK_LABEL_WIDTH + EMPTY_TIMELINE_WIDTH;

  useEffect(() => {
    if (source) select(source);
  }, [select, source]);

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

  function seekFromPointer(clientX: number) {
    const viewport = viewportRef.current;
    if (!viewport || !source || duration <= 0) return;
    seek(timelineTimeFromPointer({
      clientX: clientX - TRACK_LABEL_WIDTH,
      viewportLeft: viewport.getBoundingClientRect().left,
      scrollLeft: viewport.scrollLeft,
      pixelsPerSecond,
      duration,
    }));
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
          <div
            className="timeline-ruler"
            aria-label="초 단위 Timeline ruler"
            onClick={(event) => seekFromPointer(event.clientX)}
          >
            {ticks.map((tick) => (
              <span key={tick} style={{ left: TRACK_LABEL_WIDTH + tick * pixelsPerSecond }}>
                {formatTimelineTime(tick)}
              </span>
            ))}
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
            style={{ left: TRACK_LABEL_WIDTH + currentTime * pixelsPerSecond }}
            aria-hidden="true"
          />
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
          {formatTimelineTime(currentTime)} / {duration > 0 ? formatTimelineTime(duration) : "길이 확인 전"}
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
