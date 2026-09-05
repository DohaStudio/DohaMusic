import { dohaApi } from "@/services/doha-api";
import { ApiError } from "@/services/api-client";

export type WorkingCommand =
  | { type: "TRACK_CREATE"; trackId: string; trackOrder: number }
  | { type: "TRACK_RENAME"; trackId: string; before: string; after: string }
  | { type: "TRACK_REORDER"; before: string[]; after: string[] }
  | { type: "TRACK_DELETE"; trackId: string; trackOrder: number }
  | { type: "CLIP_CREATE"; clipId: string }
  | { type: "CLIP_COPY"; sourceClipId: string; copiedClipId: string; targetTrackId: string; targetTimelineStart: string }
  | { type: "CLIP_MOVE"; clipId: string; before: string; after: string }
  | { type: "CLIP_GAIN"; clipId: string; beforeGainDb: string; afterGainDb: string }
  | { type: "CLIP_FADE"; clipId: string; before: ClipFade; after: ClipFade }
  | { type: "CLIP_LOOP"; clipId: string; before: ClipLoop; after: ClipLoop }
  | { type: "CLIP_TRIM_START"; clipId: string; before: ClipStart; after: ClipStart }
  | { type: "CLIP_TRIM_END"; clipId: string; before: string; after: string }
  | { type: "CLIP_DELETE"; clipId: string }
  | { type: "CLIP_SPLIT"; originalClipId: string; leftClipId: string; rightClipId: string };

export interface ClipStart {
  timelineStart: string;
  sourceIn: string;
}

export interface ClipFade {
  fadeIn: string;
  fadeOut: string;
}

export interface ClipLoop {
  enabled: boolean;
  timelineDuration: string;
  phase: string;
}

export interface CommandContext {
  projectId: string;
  workingCompositionId: string;
  revision: number;
  createKey: () => string;
}

export interface CommandResult {
  completedRevision: number;
}

export class MemoryCommandHistory {
  undoStack: WorkingCommand[] = [];
  redoStack: WorkingCommand[] = [];

  push(command: WorkingCommand) {
    this.undoStack = [...this.undoStack, command];
    this.redoStack = [];
  }

  completeUndo() {
    const command = this.undoStack.at(-1);
    if (!command) return;
    this.undoStack = this.undoStack.slice(0, -1);
    this.redoStack = [...this.redoStack, command];
  }

  completeRedo() {
    const command = this.redoStack.at(-1);
    if (!command) return;
    this.redoStack = this.redoStack.slice(0, -1);
    this.undoStack = [...this.undoStack, command];
  }

  clear() {
    this.undoStack = [];
    this.redoStack = [];
  }
}

export async function executeWorkingCommand(
  command: WorkingCommand,
  direction: "undo" | "redo",
  context: CommandContext,
): Promise<CommandResult> {
  const base = {
    working_composition_id: context.workingCompositionId,
    expected_revision: context.revision,
  };
  switch (command.type) {
    case "TRACK_CREATE":
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.deleteWorkingTrack(context.projectId, command.trackId, base, key))
        : await withIdempotency(context, (key) => dohaApi.restoreWorkingTrack(context.projectId, command.trackId, { ...base, target_track_order: command.trackOrder }, key)));
    case "TRACK_DELETE":
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.restoreWorkingTrack(context.projectId, command.trackId, { ...base, target_track_order: command.trackOrder }, key))
        : await withIdempotency(context, (key) => dohaApi.deleteWorkingTrack(context.projectId, command.trackId, base, key)));
    case "TRACK_RENAME":
      return revisionOf(await dohaApi.renameWorkingTrack(context.projectId, command.trackId, {
        ...base,
        name: direction === "undo" ? command.before : command.after,
      }));
    case "TRACK_REORDER":
      return revisionOf(await dohaApi.reorderWorkingTracks(context.projectId, {
        ...base,
        ordered_track_ids: direction === "undo" ? command.before : command.after,
      }));
    case "CLIP_CREATE":
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.deleteWorkingClip(context.projectId, command.clipId, base, key))
        : await withIdempotency(context, (key) => dohaApi.restoreWorkingClip(context.projectId, command.clipId, base, key)));
    case "CLIP_COPY":
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.deleteWorkingClip(context.projectId, command.copiedClipId, base, key))
        : await withIdempotency(context, (key) => dohaApi.restoreWorkingClip(context.projectId, command.copiedClipId, base, key)));
    case "CLIP_DELETE":
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.restoreWorkingClip(context.projectId, command.clipId, base, key))
        : await withIdempotency(context, (key) => dohaApi.deleteWorkingClip(context.projectId, command.clipId, base, key)));
    case "CLIP_MOVE":
      return revisionOf(await dohaApi.moveWorkingClip(context.projectId, command.clipId, {
        ...base,
        timeline_start: direction === "undo" ? command.before : command.after,
      }));
    case "CLIP_GAIN":
      return revisionOf(await withIdempotency(context, (key) => dohaApi.updateWorkingClipGain(
        context.projectId,
        command.clipId,
        { ...base, gain_db: Number(direction === "undo" ? command.beforeGainDb : command.afterGainDb) },
        key,
      )));
    case "CLIP_FADE": {
      const value = direction === "undo" ? command.before : command.after;
      return revisionOf(await withIdempotency(context, (key) => dohaApi.updateWorkingClipFade(
        context.projectId,
        command.clipId,
        { ...base, fade_in: Number(value.fadeIn), fade_out: Number(value.fadeOut) },
        key,
      )));
    }
    case "CLIP_LOOP": {
      const value = direction === "undo" ? command.before : command.after;
      return revisionOf(await withIdempotency(context, (key) => dohaApi.restoreWorkingClipLoop(
        context.projectId,
        command.clipId,
        {
          ...base,
          loop_enabled: value.enabled,
          timeline_duration: Number(value.timelineDuration),
          loop_phase: Number(value.phase),
        },
        key,
      )));
    }
    case "CLIP_TRIM_START": {
      const value = direction === "undo" ? command.before : command.after;
      return revisionOf(await dohaApi.trimWorkingClipStart(context.projectId, command.clipId, {
        ...base,
        timeline_start: value.timelineStart,
        source_in: value.sourceIn,
      }));
    }
    case "CLIP_TRIM_END":
      return revisionOf(await dohaApi.trimWorkingClipEnd(context.projectId, command.clipId, {
        ...base,
        source_out: direction === "undo" ? command.before : command.after,
      }));
    case "CLIP_SPLIT": {
      const payload = { ...base, left_clip_id: command.leftClipId, right_clip_id: command.rightClipId };
      return revisionOf(direction === "undo"
        ? await withIdempotency(context, (key) => dohaApi.unsplitWorkingClip(context.projectId, command.originalClipId, payload, key))
        : await withIdempotency(context, (key) => dohaApi.resplitWorkingClip(context.projectId, command.originalClipId, payload, key)));
    }
  }
}

function revisionOf(result: { completed_revision: number }): CommandResult {
  return { completedRevision: result.completed_revision };
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

async function withIdempotency<T>(context: CommandContext, operation: (key: string) => Promise<T>): Promise<T> {
  const key = context.createKey();
  try {
    return await operation(key);
  } catch (error) {
    if (error instanceof ApiError && ["NETWORK_ERROR", "REQUEST_TIMEOUT"].includes(error.code)) {
      return operation(key);
    }
    throw error;
  }
}
