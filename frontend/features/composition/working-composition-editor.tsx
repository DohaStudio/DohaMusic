"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Redo2, Scissors, Trash2, Undo2, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { Button, ErrorAlert, Input } from "@/components/ui";
import { usePlayerStore } from "@/stores/player-store";
import { ApiError, userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import type { CompositionReadItemDto, WorkingClipDto, WorkingCompositionDto, WorkingTrackDto } from "@/types/api";
import { buildWaveformPath, loadWaveformPeaks, type WaveformLoader } from "./waveform";
import {
  projectWaveformWindow,
  useWorkingWaveforms,
  waveformProjectionSignature,
  type MediaSourceResolver,
} from "./working-waveform";
import {
  executeWorkingCommand,
  MemoryCommandHistory,
  newIdempotencyKey,
  type WorkingCommand,
} from "./working-composition-history";
import { WorkingPreviewControl } from "./working-preview-control";

const MIN_PIXELS_PER_SECOND = 32;
const MAX_PIXELS_PER_SECOND = 128;
const DEFAULT_PIXELS_PER_SECOND = 64;

export function WorkingCompositionEditor({
  projectId,
  snapshotId,
  sources,
  mediaSourceResolver,
  waveformLoader = loadWaveformPeaks,
}: {
  projectId: string;
  snapshotId: string;
  sources: CompositionReadItemDto[];
  mediaSourceResolver?: MediaSourceResolver;
  waveformLoader?: WaveformLoader;
}) {
  return <WorkingCompositionEditorSession
    key={projectId}
    projectId={projectId}
    snapshotId={snapshotId}
    sources={sources}
    mediaSourceResolver={mediaSourceResolver}
    waveformLoader={waveformLoader}
  />;
}

function WorkingCompositionEditorSession({
  projectId,
  snapshotId,
  sources,
  mediaSourceResolver,
  waveformLoader,
}: {
  projectId: string;
  snapshotId: string;
  sources: CompositionReadItemDto[];
  mediaSourceResolver?: MediaSourceResolver;
  waveformLoader: WaveformLoader;
}) {
  const queryClient = useQueryClient();
  const [history, setHistory] = useState(() => new MemoryCommandHistory());
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [trackName, setTrackName] = useState("");
  const [sourceVersionId, setSourceVersionId] = useState(sources[0]?.asset_version.asset_version_id ?? "");
  const [sourceIn, setSourceIn] = useState("0");
  const [sourceOut, setSourceOut] = useState("10");
  const [timelineStart, setTimelineStart] = useState("0");
  const [copyTargetTrackId, setCopyTargetTrackId] = useState("");
  const [copyTimelineStart, setCopyTimelineStart] = useState("");
  const [draggedTrackId, setDraggedTrackId] = useState<string | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(DEFAULT_PIXELS_PER_SECOND);
  const playhead = usePlayerStore((state) => state.currentTime);
  const queryKey = useMemo(() => ["working-composition", projectId] as const, [projectId]);
  const working = useQuery({
    queryKey,
    queryFn: ({ signal }) => dohaApi.getWorkingComposition(projectId, signal),
    retry: false,
  });
  const noWorkingComposition = working.error instanceof ApiError
    && working.error.code === "WORKING_COMPOSITION_NOT_FOUND";
  const data = working.data;

  const clearHistory = useCallback(() => {
    setHistory(new MemoryCommandHistory());
  }, []);

  const reconcile = useCallback(async (clear = false) => {
    const canonical = await dohaApi.getWorkingComposition(projectId);
    queryClient.setQueryData(queryKey, canonical);
    if (clear) clearHistory();
    return canonical;
  }, [clearHistory, projectId, queryClient, queryKey]);

  const fail = useCallback(async (cause: unknown, preserveHistory = false) => {
    const apiError = cause instanceof ApiError ? cause : null;
    if (apiError?.code === "WORKING_COMPOSITION_REVISION_CONFLICT"
      || apiError?.code === "SPLIT_STRUCTURE_CONFLICT"
      || apiError?.code === "NETWORK_ERROR"
      || apiError?.code === "REQUEST_TIMEOUT") {
      try {
        const clear = !preserveHistory
          || apiError?.code === "WORKING_COMPOSITION_REVISION_CONFLICT"
          || apiError?.code === "SPLIT_STRUCTURE_CONFLICT";
        await reconcile(clear);
        setMessage(clear
          ? "서버의 최신 편집 상태를 불러왔습니다. Undo/Redo 기록은 초기화되었습니다."
          : "서버의 최신 편집 상태를 불러왔습니다. 기존 Undo/Redo 기록은 유지됩니다.");
      } catch {
        // The original structured error remains the useful failure.
      }
    }
    setError(workingErrorMessage(cause));
  }, [reconcile]);

  async function mutate<T extends { completed_revision: number }>(
    operation: () => Promise<T>,
    command?: (result: T, before: WorkingCompositionDto) => WorkingCommand,
    clearAfter = false,
    preserveHistoryOnFailure = false,
  ) {
    if (!data || pending) return false;
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const result = await operation();
      queryClient.setQueryData<WorkingCompositionDto>(queryKey, { ...data, revision: result.completed_revision });
      if (clearAfter) clearHistory();
      await reconcile(false);
      if (command) {
        setHistory((current) => {
          const next = copyHistory(current);
          next.push(command(result, data));
          return next;
        });
      }
      return true;
    } catch (cause) {
      await fail(cause, preserveHistoryOnFailure);
      return false;
    } finally {
      setPending(false);
    }
  }

  async function initialize() {
    if (pending) return;
    setPending(true);
    setError(null);
    const key = newIdempotencyKey();
    try {
      const result = await retryIdempotent(() => dohaApi.initializeWorkingComposition(projectId, key));
      await reconcile(true);
      setMessage(`편집 공간을 시작했습니다. revision ${result.completed_revision}`);
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "WORKING_COMPOSITION_ALREADY_EXISTS") {
        try { await reconcile(true); } catch { /* retain product conflict */ }
      }
      await fail(cause);
    } finally {
      setPending(false);
    }
  }

  async function commitComposition() {
    if (!data || pending || data.clips.length === 0) return;
    const success = await mutate(
      () => withIdempotency((key) => dohaApi.commitWorkingComposition(
        projectId,
        data.revision,
        key,
      )),
      undefined,
      true,
      true,
    );
    if (!success) return;
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project-composition", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project-composition-snapshots", projectId] }),
    ]);
    setMessage("현재 편집 상태를 새 버전으로 저장했습니다. Undo/Redo 기록이 초기화되었습니다.");
  }

  async function copySelectedClip() {
    if (!data || !selectedClip || pending || !copyTargetTrackId || copyTimelineStart === "") return;
    let copiedClipId: string | null = null;
    const success = await mutate(
      () => withIdempotency((key) => dohaApi.copyWorkingClip(
        projectId,
        selectedClip.clip_id,
        {
          working_composition_id: data.working_composition_id,
          expected_revision: data.revision,
          target_track_id: copyTargetTrackId,
          target_timeline_start: copyTimelineStart,
        },
        key,
      )).then((result) => {
        copiedClipId = result.clip_id;
        return result;
      }),
      (result) => ({
        type: "CLIP_COPY",
        sourceClipId: selectedClip.clip_id,
        copiedClipId: result.clip_id,
        targetTrackId: copyTargetTrackId,
        targetTimelineStart: copyTimelineStart,
      }),
    );
    if (success && copiedClipId) {
      setSelectedClipId(copiedClipId);
      setMessage(`Clip을 ${copyTimelineStart}s 위치에 복사했습니다.`);
    }
  }

  async function runHistory(direction: "undo" | "redo") {
    if (!data || pending) return;
    const stack = direction === "undo" ? history.undoStack : history.redoStack;
    const command = stack.at(-1);
    if (!command) return;
    setPending(true);
    setError(null);
    try {
      const result = await executeWorkingCommand(command, direction, {
        projectId,
        workingCompositionId: data.working_composition_id,
        revision: data.revision,
        createKey: newIdempotencyKey,
      });
      queryClient.setQueryData<WorkingCompositionDto>(queryKey, { ...data, revision: result.completedRevision });
      await reconcile(false);
      setHistory((current) => {
        const next = copyHistory(current);
        if (direction === "undo") next.completeUndo();
        else next.completeRedo();
        return next;
      });
    } catch (cause) {
      await fail(cause);
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target) || pending || (!event.ctrlKey && !event.metaKey)) return;
      const undo = event.key.toLowerCase() === "z" && !event.shiftKey;
      const redo = (event.key.toLowerCase() === "z" && event.shiftKey) || event.key.toLowerCase() === "y";
      if (!undo && !redo) return;
      event.preventDefault();
      void runHistory(undo ? "undo" : "redo");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  if (working.isPending) return <p role="status">WorkingComposition을 불러오는 중입니다.</p>;
  if (noWorkingComposition) {
    return (
      <section className="working-editor-empty" aria-labelledby="working-editor-title">
        <h4 id="working-editor-title">Clip 편집 공간</h4>
        <p>아직 WorkingComposition이 없습니다. 자동 생성하지 않으며, 아래 버튼으로 명시적으로 시작합니다.</p>
        {error && <ErrorAlert title="편집 공간을 시작하지 못했습니다." message={error} />}
        <Button type="button" disabled aria-label="Working Preview 만들기">Preview 만들기</Button>
        <Button type="button" disabled={pending} onClick={() => void initialize()}>
          {pending ? "시작 중…" : "WorkingComposition 시작"}
        </Button>
      </section>
    );
  }
  if (working.error || !data) {
    return <ErrorAlert title="WorkingComposition을 불러오지 못했습니다." message={workingErrorMessage(working.error)} />;
  }

  const selectedTrack = data.tracks.find((track) => track.track_id === selectedTrackId) ?? data.tracks[0];
  const selectedClip = data.clips.find((clip) => clip.clip_id === selectedClipId) ?? null;
  const selectedSplitAt = selectedClip
    ? Number(selectedClip.source_in) + playhead - Number(selectedClip.timeline_start)
    : 0;
  const base = { working_composition_id: data.working_composition_id, expected_revision: data.revision };

  return (
    <section className="working-editor" aria-labelledby="working-editor-title">
      <header className="working-editor-toolbar">
        <div>
          <p className="eyebrow">WORKING COMPOSITION</p>
          <h4 id="working-editor-title">Track / Clip Editor</h4>
          <span>revision {data.revision} · 저장됨 · Undo/Redo는 이 탭의 메모리에만 유지</span>
        </div>
        <div className="working-history-controls">
          <div className="working-zoom-controls" aria-label="Clip Timeline 확대 및 축소">
            <button
              type="button"
              aria-label="Clip Timeline 축소"
              disabled={pixelsPerSecond === MIN_PIXELS_PER_SECOND}
              onClick={() => setPixelsPerSecond((value) => Math.max(MIN_PIXELS_PER_SECOND, value - 16))}
            ><ZoomOut aria-hidden="true" /></button>
            <output aria-label="Clip Timeline 배율">{pixelsPerSecond}px/s</output>
            <button
              type="button"
              aria-label="Clip Timeline 확대"
              disabled={pixelsPerSecond === MAX_PIXELS_PER_SECOND}
              onClick={() => setPixelsPerSecond((value) => Math.min(MAX_PIXELS_PER_SECOND, value + 16))}
            ><ZoomIn aria-hidden="true" /></button>
          </div>
          <button type="button" aria-label="편집 실행 취소" disabled={pending || history.undoStack.length === 0} onClick={() => void runHistory("undo")}><Undo2 aria-hidden="true" /> Undo</button>
          <button type="button" aria-label="편집 다시 실행" disabled={pending || history.redoStack.length === 0} onClick={() => void runHistory("redo")}><Redo2 aria-hidden="true" /> Redo</button>
          <Button
            type="button"
            disabled={pending || data.clips.length === 0}
            onClick={() => void commitComposition()}
          >현재 편집 상태를 새 버전으로 저장</Button>
          <Button type="button" disabled={pending} onClick={() => void mutate(
            () => withIdempotency((key) => dohaApi.checkoutWorkingComposition(projectId, { ...base, composition_snapshot_id: snapshotId }, key)),
            undefined,
            true,
          )}>현재 Snapshot Checkout</Button>
        </div>
      </header>
      {message && <p className="working-editor-notice" role="status">{message}</p>}
      {error && <ErrorAlert title="편집을 적용하지 못했습니다." message={error} />}
      {data.clips.length === 0 && (
        <p className="working-editor-notice">활성 Clip을 하나 이상 배치하면 새 버전으로 저장할 수 있습니다.</p>
      )}

      <WorkingPreviewControl
        projectId={projectId}
        workingCompositionId={data.working_composition_id}
        currentRevision={data.revision}
        clipCount={data.clips.length}
        onRevisionConflict={async () => {
          await reconcile(true);
          setMessage("최신 편집 상태를 불러왔습니다. Preview를 다시 실행해 주세요.");
        }}
      />

      <form className="working-add-track" onSubmit={(event) => {
        event.preventDefault();
        const name = trackName.trim();
        if (!name) return;
        void mutate(
          () => withIdempotency((key) => dohaApi.createWorkingTrack(projectId, { ...base, name }, key)),
          (result) => ({ type: "TRACK_CREATE", trackId: result.track_id, trackOrder: data.tracks.length }),
        ).then((success) => { if (success) setTrackName(""); });
      }}>
        <Input aria-label="새 Track 이름" value={trackName} disabled={pending} onChange={(event) => setTrackName(event.target.value)} />
        <Button type="submit" disabled={pending || !trackName.trim()}>Track 추가</Button>
      </form>

      <div className="working-track-list" role="list" aria-label="편집 Track 목록">
        {data.tracks.map((track) => (
          <TrackRow
            key={track.track_id}
            track={track}
            selected={track.track_id === selectedTrack?.track_id}
            pending={pending}
            onSelect={() => setSelectedTrackId(track.track_id)}
            onRename={(name) => void mutate(
              () => dohaApi.renameWorkingTrack(projectId, track.track_id, { ...base, name }),
              () => ({ type: "TRACK_RENAME", trackId: track.track_id, before: track.name, after: name }),
            )}
            onDelete={() => void mutate(
              () => withIdempotency((key) => dohaApi.deleteWorkingTrack(projectId, track.track_id, base, key)),
              () => ({ type: "TRACK_DELETE", trackId: track.track_id, trackOrder: track.track_order }),
            )}
            onDragStart={() => setDraggedTrackId(track.track_id)}
            onDrop={() => {
              if (!draggedTrackId || draggedTrackId === track.track_id) return;
              const before = data.tracks.map((item) => item.track_id);
              const after = moveBefore(before, draggedTrackId, track.track_id);
              setDraggedTrackId(null);
              void mutate(
                () => dohaApi.reorderWorkingTracks(projectId, { ...base, ordered_track_ids: after }),
                () => ({ type: "TRACK_REORDER", before, after }),
              );
            }}
          />
        ))}
      </div>

      {selectedTrack ? (
        <>
          <form className="working-add-clip" onSubmit={(event) => {
            event.preventDefault();
            void mutate(
              () => withIdempotency((key) => dohaApi.createWorkingClip(projectId, {
                ...base,
                track_id: selectedTrack.track_id,
                source_asset_version_id: sourceVersionId,
                timeline_start: timelineStart,
                source_in: sourceIn,
                source_out: sourceOut,
              }, key)),
              (result) => ({ type: "CLIP_CREATE", clipId: result.clip_id }),
            );
          }}>
            <label>exact AssetVersion<select aria-label="Clip source AssetVersion" value={sourceVersionId} disabled={pending} onChange={(event) => setSourceVersionId(event.target.value)}>{sources.map((item) => <option key={item.asset_version.asset_version_id} value={item.asset_version.asset_version_id}>{item.item_role} · v{item.asset_version.version_number}</option>)}</select></label>
            <label>Timeline start<Input aria-label="Clip timeline start" type="number" min="0" step="0.001" value={timelineStart} onChange={(event) => setTimelineStart(event.target.value)} /></label>
            <label>Source in<Input aria-label="Clip source in" type="number" min="0" step="0.001" value={sourceIn} onChange={(event) => setSourceIn(event.target.value)} /></label>
            <label>Source out<Input aria-label="Clip source out" type="number" min="0.001" step="0.001" value={sourceOut} onChange={(event) => setSourceOut(event.target.value)} /></label>
            <Button type="submit" disabled={pending || !sourceVersionId}>Clip 배치</Button>
          </form>
          <ClipLane
            projectId={projectId}
            workingCompositionId={data.working_composition_id}
            track={selectedTrack}
            clips={data.clips.filter((clip) => clip.track_id === selectedTrack.track_id)}
            selectedClipId={selectedClipId}
            pending={pending}
            pixelsPerSecond={pixelsPerSecond}
            playhead={playhead}
            mediaSourceResolver={mediaSourceResolver}
            waveformLoader={waveformLoader}
            onSelect={(clipId) => {
              const clip = data.clips.find((item) => item.clip_id === clipId);
              setSelectedClipId(clipId);
              setCopyTargetTrackId(clip?.track_id ?? "");
              setCopyTimelineStart("");
            }}
            onMove={(clip, next) => void mutate(
              () => dohaApi.moveWorkingClip(projectId, clip.clip_id, { ...base, timeline_start: next }),
              () => ({ type: "CLIP_MOVE", clipId: clip.clip_id, before: clip.timeline_start, after: next }),
            )}
            onTrimStart={(clip, nextTimeline, nextSource) => void mutate(
              () => dohaApi.trimWorkingClipStart(projectId, clip.clip_id, { ...base, timeline_start: nextTimeline, source_in: nextSource }),
              () => ({ type: "CLIP_TRIM_START", clipId: clip.clip_id, before: { timelineStart: clip.timeline_start, sourceIn: clip.source_in }, after: { timelineStart: nextTimeline, sourceIn: nextSource } }),
            )}
            onTrimEnd={(clip, next) => void mutate(
              () => dohaApi.trimWorkingClipEnd(projectId, clip.clip_id, { ...base, source_out: next }),
              () => ({ type: "CLIP_TRIM_END", clipId: clip.clip_id, before: clip.source_out, after: next }),
            )}
          />
        </>
      ) : <p className="working-editor-notice">Clip을 배치하려면 Track을 먼저 추가하세요.</p>}

      {selectedClip && (
        <div className="working-clip-controls" aria-label="선택 Clip 편집">
          <strong>선택 Clip {shortId(selectedClip.clip_id)}</strong>
          <Button type="button" disabled={pending || !(selectedSplitAt > Number(selectedClip.source_in) && selectedSplitAt < Number(selectedClip.source_out))} onClick={() => void mutate(
            () => withIdempotency((key) => dohaApi.splitWorkingClip(projectId, selectedClip.clip_id, { ...base, split_at: seconds(selectedSplitAt) }, key)),
            (result) => ({ type: "CLIP_SPLIT", originalClipId: result.original_clip_id, leftClipId: result.left_clip_id, rightClipId: result.right_clip_id }),
          ).then((success) => { if (success) setSelectedClipId(null); })}><Scissors aria-hidden="true" /> Playhead에서 Split ({seconds(playhead)}s)</Button>
          <Button type="button" disabled={pending} onClick={() => void mutate(
            () => withIdempotency((key) => dohaApi.deleteWorkingClip(projectId, selectedClip.clip_id, base, key)),
            () => ({ type: "CLIP_DELETE", clipId: selectedClip.clip_id }),
          ).then((success) => { if (success) setSelectedClipId(null); })}><Trash2 aria-hidden="true" /> Clip 삭제</Button>
        </div>
      )}
      <div className="working-clip-controls" aria-label="Clip Copy destination">
        <strong>Clip Copy</strong>
        <p id="clip-copy-help">
          {!selectedClip
            ? "Copy할 Clip을 먼저 선택하세요."
            : copyTimelineStart === ""
              ? "대상 Track과 Timeline 위치를 명시하거나 현재 Playhead를 사용하세요."
              : `대상 위치 ${copyTimelineStart}s를 확인한 뒤 복사하세요.`}
        </p>
        <label>
          Copy 대상 Track
          <select
            aria-label="Copy 대상 Track"
            value={copyTargetTrackId}
            disabled={pending || !selectedClip}
            onChange={(event) => setCopyTargetTrackId(event.target.value)}
          >
            <option value="">Track 선택</option>
            {data.tracks.map((track) => (
              <option key={track.track_id} value={track.track_id}>{track.name}</option>
            ))}
          </select>
        </label>
        <label>
          Copy Timeline start
          <Input
            aria-label="Copy Timeline start"
            type="number"
            min="0"
            step="0.001"
            value={copyTimelineStart}
            disabled={pending || !selectedClip}
            onChange={(event) => setCopyTimelineStart(event.target.value)}
          />
        </label>
        <Button
          type="button"
          disabled={pending || !selectedClip}
          onClick={() => setCopyTimelineStart(seconds(playhead))}
        >현재 Playhead {seconds(playhead)}s 사용</Button>
        <Button
          type="button"
          aria-label="선택 Clip을 명시한 위치에 복사"
          aria-describedby="clip-copy-help"
          disabled={pending || !selectedClip || !copyTargetTrackId || copyTimelineStart === "" || Number(copyTimelineStart) < 0}
          onClick={() => void copySelectedClip()}
        ><Copy aria-hidden="true" /> Clip 복사</Button>
      </div>
    </section>
  );
}

function TrackRow({ track, selected, pending, onSelect, onRename, onDelete, onDragStart, onDrop }: {
  track: WorkingTrackDto; selected: boolean; pending: boolean; onSelect: () => void; onRename: (name: string) => void; onDelete: () => void; onDragStart: () => void; onDrop: () => void;
}) {
  return <article role="listitem" className={`working-track-row${selected ? " selected" : ""}`} draggable={!pending} onDragStart={onDragStart} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
    <button type="button" aria-pressed={selected} aria-label={`${track.name} Track 선택`} onClick={onSelect}>↕ {track.track_order + 1}</button>
    <Input key={track.name} aria-label={`${track.name} Track 이름`} defaultValue={track.name} disabled={pending} onBlur={(event) => { const next = event.currentTarget.value.trim(); if (next && next !== track.name) onRename(next); }} />
    <button type="button" aria-label={`${track.name} Track 삭제`} disabled={pending} onClick={onDelete}><Trash2 aria-hidden="true" /></button>
  </article>;
}

function ClipLane({ projectId, workingCompositionId, track, clips, selectedClipId, pending, pixelsPerSecond, playhead, mediaSourceResolver, waveformLoader, onSelect, onMove, onTrimStart, onTrimEnd }: {
  projectId: string; workingCompositionId: string; track: WorkingTrackDto; clips: WorkingClipDto[]; selectedClipId: string | null; pending: boolean;
  pixelsPerSecond: number; playhead: number; mediaSourceResolver?: MediaSourceResolver; waveformLoader: WaveformLoader;
  onSelect: (id: string) => void; onMove: (clip: WorkingClipDto, value: string) => void;
  onTrimStart: (clip: WorkingClipDto, timeline: string, source: string) => void; onTrimEnd: (clip: WorkingClipDto, source: string) => void;
}) {
  const waveformFor = useWorkingWaveforms({
    projectId,
    workingCompositionId,
    assetVersionIds: clips.map((clip) => clip.source_asset_version_id),
    resolver: mediaSourceResolver,
    loader: waveformLoader,
  });
  const [preview, setPreview] = useState<{ clipId: string; mode: "move" | "start" | "end"; delta: number } | null>(null);
  const drag = useRef<{ pointerId: number; startX: number; clip: WorkingClipDto; mode: "move" | "start" | "end" } | null>(null);
  const finish = (event: ReactPointerEvent<HTMLElement>, cancelled = false) => {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    drag.current = null;
    const delta = (event.clientX - active.startX) / pixelsPerSecond;
    setPreview(null);
    if (cancelled || Math.abs(delta) < 0.001) return;
    if (active.mode === "move") onMove(active.clip, seconds(Math.max(0, Number(active.clip.timeline_start) + delta)));
    if (active.mode === "start") {
      const bounded = Math.max(
        -Math.min(Number(active.clip.timeline_start), Number(active.clip.source_in)),
        Math.min(delta, Number(active.clip.source_out) - Number(active.clip.source_in) - 0.001),
      );
      onTrimStart(active.clip, seconds(Math.max(0, Number(active.clip.timeline_start) + bounded)), seconds(Number(active.clip.source_in) + bounded));
    }
    if (active.mode === "end") {
      const bounded = Math.max(
        Number(active.clip.source_in) - Number(active.clip.source_out) + 0.001,
        Math.min(delta, Number(active.clip.source_duration) - Number(active.clip.source_out)),
      );
      onTrimEnd(active.clip, seconds(Number(active.clip.source_out) + bounded));
    }
  };
  const start = (event: ReactPointerEvent<HTMLElement>, clip: WorkingClipDto, mode: "move" | "start" | "end") => {
    if (pending) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { pointerId: event.pointerId, startX: event.clientX, clip, mode };
    setPreview({ clipId: clip.clip_id, mode, delta: 0 });
  };
  const move = (event: ReactPointerEvent<HTMLElement>) => {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    setPreview({ clipId: active.clip.clip_id, mode: active.mode, delta: (event.clientX - active.startX) / pixelsPerSecond });
  };
  const width = Math.max(720, ...clips.map((clip) => (Number(clip.timeline_start) + Number(clip.source_out) - Number(clip.source_in)) * pixelsPerSecond + 80));
  return <div className="working-clip-scroll" data-testid="working-clip-scroll"><div className="working-clip-lane" style={{ width, backgroundSize: `${pixelsPerSecond}px 100%` }} aria-label={`${track.name} Clip lane`}>
    {clips.map((clip) => {
      const delta = preview?.clipId === clip.clip_id ? preview.delta : 0;
      const startDelta = preview?.mode === "start" ? delta : 0;
      const endDelta = preview?.mode === "end" ? delta : 0;
      const left = (Number(clip.timeline_start) + (preview?.mode === "move" ? delta : startDelta)) * pixelsPerSecond;
      const duration = Number(clip.source_out) - Number(clip.source_in) - startDelta + endDelta;
      const sourceIn = Number(clip.source_in) + startDelta;
      const sourceOut = Number(clip.source_out) + endDelta;
      const waveform = waveformFor(clip.source_asset_version_id);
      const projection = waveform.status === "ready"
        ? projectWaveformWindow(
          waveform.waveform,
          sourceIn,
          sourceOut,
          undefined,
          Number(clip.source_duration),
        )
        : [];
      return <button key={clip.clip_id} type="button" className={`working-clip${selectedClipId === clip.clip_id ? " selected" : ""}`} style={{ left, width: Math.max(duration * pixelsPerSecond, 24) }} aria-label={`Clip ${shortId(clip.clip_id)} 선택 및 이동`} aria-pressed={selectedClipId === clip.clip_id} onClick={() => onSelect(clip.clip_id)} onPointerDown={(event) => start(event, clip, "move")} onPointerMove={move} onPointerUp={finish} onPointerCancel={(event) => finish(event, true)}>
        <span className="working-trim-handle start" aria-label={`Clip ${shortId(clip.clip_id)} 시작 Trim`} onPointerDown={(event) => start(event, clip, "start")} />
        <span
          className={`working-clip-waveform ${waveform.status}`}
          aria-hidden="true"
          data-testid={`clip-waveform-${clip.clip_id}`}
          data-waveform-status={waveform.status}
          data-source-window={`${seconds(sourceIn)}:${seconds(sourceOut)}`}
          data-waveform-signature={projection.length ? waveformProjectionSignature(projection) : undefined}
        >
          {waveform.status === "loading" && <span>loading</span>}
          {waveform.status === "unavailable" && <span>unavailable</span>}
          {waveform.status === "ready" && projection.length > 0 && (
            <svg viewBox="0 0 1000 64" preserveAspectRatio="none">
              <path d={buildWaveformPath(projection, 1000, 64)} />
            </svg>
          )}
        </span>
        <strong>{shortId(clip.clip_id)}</strong><small>{seconds(duration)}s</small>
        <span className="working-trim-handle end" aria-label={`Clip ${shortId(clip.clip_id)} 끝 Trim`} onPointerDown={(event) => start(event, clip, "end")} />
      </button>;
    })}
    <span
      className="working-clip-playhead"
      aria-hidden="true"
      style={{ left: Math.max(0, playhead) * pixelsPerSecond }}
    />
  </div></div>;
}

async function retryIdempotent<T>(operation: () => Promise<T>): Promise<T> {
  try { return await operation(); } catch (error) {
    if (error instanceof ApiError && ["NETWORK_ERROR", "REQUEST_TIMEOUT"].includes(error.code)) return operation();
    throw error;
  }
}

function withIdempotency<T>(operation: (key: string) => Promise<T>): Promise<T> {
  const key = newIdempotencyKey();
  return retryIdempotent(() => operation(key));
}

function workingErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      WORKING_COMPOSITION_ALREADY_EXISTS: "이미 편집 공간이 있습니다. 서버 상태를 다시 불러왔습니다.",
      WORKING_COMPOSITION_REVISION_CONFLICT: "다른 변경으로 revision이 달라졌습니다.",
      WORKING_COMPOSITION_EMPTY: "활성 Clip을 하나 이상 배치한 뒤 새 버전으로 저장해 주세요.",
      TRACK_NOT_EMPTY: "Clip이 있는 Track은 삭제할 수 없습니다.",
      CLIP_OVERLAP: "같은 Track의 다른 Clip과 겹칩니다.",
      INVALID_CLIP_RANGE: "Clip 시간 범위를 확인해 주세요.",
      SOURCE_ASSET_UNAVAILABLE: "선택한 source AssetVersion을 현재 사용할 수 없습니다.",
      SOURCE_ARTIFACT_AMBIGUOUS: "사용 가능한 source Artifact를 하나로 확정할 수 없습니다.",
      SOURCE_DURATION_UNAVAILABLE: "신뢰할 수 있는 source 길이가 없습니다.",
      SPLIT_STRUCTURE_CONFLICT: "Split 이후 구조가 달라져 Undo/Redo할 수 없습니다.",
      IDEMPOTENCY_KEY_REUSED: "동일 요청 키가 다른 편집에 사용되었습니다.",
      IDEMPOTENCY_IN_PROGRESS: "같은 편집 요청이 아직 처리 중입니다.",
    };
    return messages[error.code] ?? userErrorMessage(error);
  }
  return userErrorMessage(error);
}

function seconds(value: number): string { return Math.max(0, value).toFixed(3); }
function shortId(value: string): string { return value.slice(0, 8); }
function moveBefore(items: string[], source: string, target: string): string[] {
  const next = items.filter((item) => item !== source);
  next.splice(next.indexOf(target), 0, source);
  return next;
}
function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}

function copyHistory(source: MemoryCommandHistory): MemoryCommandHistory {
  const history = new MemoryCommandHistory();
  history.undoStack = [...source.undoStack];
  history.redoStack = [...source.redoStack];
  return history;
}
