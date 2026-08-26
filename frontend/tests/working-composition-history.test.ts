import { beforeEach, describe, expect, it, vi } from "vitest";
import { dohaApi } from "@/services/doha-api";
import { executeWorkingCommand, MemoryCommandHistory } from "@/features/composition/working-composition-history";

describe("WorkingComposition memory command history", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("successful command push, new command redo clear, undo/redo 이동과 clear를 보존한다", () => {
    const history = new MemoryCommandHistory();
    const first = { type: "CLIP_DELETE" as const, clipId: "clip-1" };
    const second = { type: "TRACK_RENAME" as const, trackId: "track-1", before: "A", after: "B" };
    history.push(first);
    history.completeUndo();
    expect(history.redoStack).toEqual([first]);
    history.completeRedo();
    expect(history.undoStack).toEqual([first]);
    history.completeUndo();
    history.push(second);
    expect(history.redoStack).toEqual([]);
    history.clear();
    expect(history.undoStack).toEqual([]);
  });

  it("실패한 Undo는 stack top을 이동시키지 않는다", async () => {
    const history = new MemoryCommandHistory();
    const command = { type: "CLIP_DELETE" as const, clipId: "clip-1" };
    history.push(command);
    vi.spyOn(dohaApi, "restoreWorkingClip").mockRejectedValue(new Error("source ineligible"));
    await expect(executeWorkingCommand(command, "undo", context(1))).rejects.toThrow("source ineligible");
    expect(history.undoStack).toEqual([command]);
    expect(history.redoStack).toEqual([]);
  });

  it("Track create undo는 delete, redo는 같은 ID restore와 원래 order를 사용한다", async () => {
    const remove = vi.spyOn(dohaApi, "deleteWorkingTrack").mockResolvedValue({ track_id: "track-1", completed_revision: 3, replayed: false });
    const restore = vi.spyOn(dohaApi, "restoreWorkingTrack").mockResolvedValue({ track_id: "track-1", completed_revision: 4, replayed: false });
    const command = { type: "TRACK_CREATE" as const, trackId: "track-1", trackOrder: 2 };
    await executeWorkingCommand(command, "undo", context(2));
    await executeWorkingCommand(command, "redo", context(3));
    expect(remove).toHaveBeenCalledWith("project-1", "track-1", expect.objectContaining({ expected_revision: 2 }), expect.any(String));
    expect(restore).toHaveBeenCalledWith("project-1", "track-1", expect.objectContaining({ target_track_order: 2, expected_revision: 3 }), expect.any(String));
  });

  it("Track rename/reorder가 absolute before/after state를 왕복한다", async () => {
    const rename = vi.spyOn(dohaApi, "renameWorkingTrack").mockResolvedValue({ track_id: "track-1", completed_revision: 2, replayed: false });
    const reorder = vi.spyOn(dohaApi, "reorderWorkingTracks").mockResolvedValue({ working_composition_id: "working-1", completed_revision: 3 });
    const renameCommand = { type: "TRACK_RENAME" as const, trackId: "track-1", before: "old", after: "new" };
    await executeWorkingCommand(renameCommand, "undo", context(1));
    await executeWorkingCommand(renameCommand, "redo", context(2));
    expect(rename.mock.calls.map((call) => call[2].name)).toEqual(["old", "new"]);
    const reorderCommand = { type: "TRACK_REORDER" as const, before: ["a", "b"], after: ["b", "a"] };
    await executeWorkingCommand(reorderCommand, "undo", context(2));
    await executeWorkingCommand(reorderCommand, "redo", context(3));
    expect(reorder.mock.calls.map((call) => call[1].ordered_track_ids)).toEqual([["a", "b"], ["b", "a"]]);
  });

  it("Clip create/delete는 restore로 same ID를 보존하고 move/trim은 geometry를 왕복한다", async () => {
    const remove = vi.spyOn(dohaApi, "deleteWorkingClip").mockResolvedValue({ clip_id: "clip-1", completed_revision: 2, replayed: false });
    const restore = vi.spyOn(dohaApi, "restoreWorkingClip").mockResolvedValue({ clip_id: "clip-1", completed_revision: 3, replayed: false });
    const move = vi.spyOn(dohaApi, "moveWorkingClip").mockResolvedValue({ clip_id: "clip-1", completed_revision: 4, replayed: false });
    const trimStart = vi.spyOn(dohaApi, "trimWorkingClipStart").mockResolvedValue({ clip_id: "clip-1", completed_revision: 5, replayed: false });
    const trimEnd = vi.spyOn(dohaApi, "trimWorkingClipEnd").mockResolvedValue({ clip_id: "clip-1", completed_revision: 6, replayed: false });
    await executeWorkingCommand({ type: "CLIP_CREATE", clipId: "clip-1" }, "undo", context(1));
    await executeWorkingCommand({ type: "CLIP_CREATE", clipId: "clip-1" }, "redo", context(2));
    await executeWorkingCommand({ type: "CLIP_DELETE", clipId: "clip-1" }, "undo", context(3));
    expect(remove).toHaveBeenCalledWith("project-1", "clip-1", expect.anything(), expect.any(String));
    expect(restore).toHaveBeenCalledTimes(2);
    await executeWorkingCommand({ type: "CLIP_MOVE", clipId: "clip-1", before: "1", after: "3" }, "undo", context(3));
    await executeWorkingCommand({ type: "CLIP_MOVE", clipId: "clip-1", before: "1", after: "3" }, "redo", context(4));
    expect(move.mock.calls.map((call) => call[2].timeline_start)).toEqual(["1", "3"]);
    await executeWorkingCommand({ type: "CLIP_TRIM_START", clipId: "clip-1", before: { timelineStart: "1", sourceIn: "0" }, after: { timelineStart: "2", sourceIn: "1" } }, "undo", context(4));
    expect(trimStart).toHaveBeenCalledWith("project-1", "clip-1", expect.objectContaining({ timeline_start: "1", source_in: "0" }));
    await executeWorkingCommand({ type: "CLIP_TRIM_END", clipId: "clip-1", before: "9", after: "8" }, "redo", context(5));
    expect(trimEnd).toHaveBeenCalledWith("project-1", "clip-1", expect.objectContaining({ source_out: "8" }));
  });

  it("split undo/redo가 exact original/left/right ID로 unsplit/resplit한다", async () => {
    const unsplit = vi.spyOn(dohaApi, "unsplitWorkingClip").mockResolvedValue(splitResult(8));
    const resplit = vi.spyOn(dohaApi, "resplitWorkingClip").mockResolvedValue(splitResult(9));
    const command = { type: "CLIP_SPLIT" as const, originalClipId: "original", leftClipId: "left", rightClipId: "right" };
    await executeWorkingCommand(command, "undo", context(7));
    await executeWorkingCommand(command, "redo", context(8));
    expect(unsplit).toHaveBeenCalledWith("project-1", "original", expect.objectContaining({ left_clip_id: "left", right_clip_id: "right" }), expect.any(String));
    expect(resplit).toHaveBeenCalledWith("project-1", "original", expect.objectContaining({ left_clip_id: "left", right_clip_id: "right" }), expect.any(String));
  });
});

function context(revision: number) {
  return { projectId: "project-1", workingCompositionId: "working-1", revision, createKey: () => `key-${revision}` };
}
function splitResult(completed_revision: number) {
  return { original_clip_id: "original", left_clip_id: "left", right_clip_id: "right", completed_revision, replayed: false };
}
