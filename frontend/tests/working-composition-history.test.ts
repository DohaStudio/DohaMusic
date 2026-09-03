import { beforeEach, describe, expect, it, vi } from "vitest";
import { dohaApi } from "@/services/doha-api";
import { ApiError } from "@/services/api-client";
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

  it("Clip Copy undo/redo는 복사본의 동일 ID를 delete/restore한다", async () => {
    const remove = vi.spyOn(dohaApi, "deleteWorkingClip").mockResolvedValue({
      clip_id: "copied-1", completed_revision: 3, replayed: false,
    });
    const restore = vi.spyOn(dohaApi, "restoreWorkingClip").mockResolvedValue({
      clip_id: "copied-1", completed_revision: 4, replayed: false,
    });
    const command = {
      type: "CLIP_COPY" as const,
      sourceClipId: "source-1",
      copiedClipId: "copied-1",
      targetTrackId: "track-2",
      targetTimelineStart: "8.250",
    };
    await executeWorkingCommand(command, "undo", context(2));
    await executeWorkingCommand(command, "redo", context(3));
    expect(remove).toHaveBeenCalledWith(
      "project-1", "copied-1", expect.objectContaining({ expected_revision: 2 }), expect.any(String),
    );
    expect(restore).toHaveBeenCalledWith(
      "project-1", "copied-1", expect.objectContaining({ expected_revision: 3 }), expect.any(String),
    );
    expect(remove).not.toHaveBeenCalledWith("project-1", "source-1", expect.anything(), expect.anything());
  });

  it("Clip Gain Undo/Redo는 같은 Clip ID와 absolute before/after 값을 사용한다", async () => {
    const update = vi.spyOn(dohaApi, "updateWorkingClipGain")
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 8, replayed: false })
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 9, replayed: false });
    const command = {
      type: "CLIP_GAIN" as const,
      clipId: "clip-1",
      beforeGainDb: "0.00",
      afterGainDb: "3.00",
    };
    await executeWorkingCommand(command, "undo", context(7));
    await executeWorkingCommand(command, "redo", context(8));
    expect(update.mock.calls.map((call) => call[1])).toEqual(["clip-1", "clip-1"]);
    expect(update.mock.calls.map((call) => call[2].gain_db)).toEqual([0, 3]);
    expect(update.mock.calls.map((call) => call[2].expected_revision)).toEqual([7, 8]);
    expect(update.mock.calls[0][3]).not.toBe(update.mock.calls[1][3]);
  });

  it("Clip Gain response-loss retry는 same key를 쓰고 실패한 Undo/Redo는 stack을 보존한다", async () => {
    const history = new MemoryCommandHistory();
    const command = {
      type: "CLIP_GAIN" as const,
      clipId: "clip-1",
      beforeGainDb: "0.00",
      afterGainDb: "3.00",
    };
    history.push(command);
    const update = vi.spyOn(dohaApi, "updateWorkingClipGain")
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "lost"))
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 8, replayed: true });
    await executeWorkingCommand(command, "undo", context(7));
    expect(update.mock.calls[0][3]).toBe(update.mock.calls[1][3]);
    expect(history.undoStack).toEqual([command]);
    expect(history.redoStack).toEqual([]);

    update.mockReset();
    update.mockRejectedValue(new Error("gain undo failed"));
    await expect(executeWorkingCommand(command, "undo", context(7))).rejects.toThrow("gain undo failed");
    expect(history.undoStack).toEqual([command]);
    expect(history.redoStack).toEqual([]);

    history.completeUndo();
    await expect(executeWorkingCommand(command, "redo", context(8))).rejects.toThrow("gain undo failed");
    expect(history.undoStack).toEqual([]);
    expect(history.redoStack).toEqual([command]);
  });

  it("Clip Fade Undo/Redo는 같은 Clip ID와 absolute before/after pair를 사용한다", async () => {
    const update = vi.spyOn(dohaApi, "updateWorkingClipFade")
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 8, replayed: false })
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 9, replayed: false });
    const command = {
      type: "CLIP_FADE" as const,
      clipId: "clip-1",
      before: { fadeIn: "0.125", fadeOut: "0.25" },
      after: { fadeIn: "0.500001", fadeOut: "0.75" },
    };
    await executeWorkingCommand(command, "undo", context(7));
    await executeWorkingCommand(command, "redo", context(8));
    expect(update.mock.calls.map((call) => call[1])).toEqual(["clip-1", "clip-1"]);
    expect(update.mock.calls.map((call) => call[2])).toEqual([
      { working_composition_id: "working-1", expected_revision: 7, fade_in: 0.125, fade_out: 0.25 },
      { working_composition_id: "working-1", expected_revision: 8, fade_in: 0.500001, fade_out: 0.75 },
    ]);
    expect(update.mock.calls[0][3]).not.toBe(update.mock.calls[1][3]);
  });

  it("Clip Fade response-loss Undo/Redo retry는 logical command별 same key를 사용한다", async () => {
    const command = {
      type: "CLIP_FADE" as const,
      clipId: "clip-1",
      before: { fadeIn: "0", fadeOut: "0" },
      after: { fadeIn: "0.5", fadeOut: "0.25" },
    };
    const update = vi.spyOn(dohaApi, "updateWorkingClipFade")
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "lost undo"))
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 8, replayed: true })
      .mockRejectedValueOnce(new ApiError(0, "REQUEST_TIMEOUT", "lost redo"))
      .mockResolvedValueOnce({ clip_id: "clip-1", completed_revision: 9, replayed: true });
    await executeWorkingCommand(command, "undo", context(7));
    await executeWorkingCommand(command, "redo", context(8));
    expect(update.mock.calls[0][3]).toBe(update.mock.calls[1][3]);
    expect(update.mock.calls[2][3]).toBe(update.mock.calls[3][3]);
    expect(update.mock.calls[1][3]).not.toBe(update.mock.calls[2][3]);
  });

  it("실패한 Clip Fade Undo/Redo는 각 stack top을 그대로 보존한다", async () => {
    const history = new MemoryCommandHistory();
    const command = {
      type: "CLIP_FADE" as const,
      clipId: "clip-1",
      before: { fadeIn: "0", fadeOut: "0" },
      after: { fadeIn: "0.5", fadeOut: "0.25" },
    };
    history.push(command);
    vi.spyOn(dohaApi, "updateWorkingClipFade").mockRejectedValue(new Error("fade failed"));
    await expect(executeWorkingCommand(command, "undo", context(7))).rejects.toThrow("fade failed");
    expect(history.undoStack).toEqual([command]);
    expect(history.redoStack).toEqual([]);
    history.completeUndo();
    await expect(executeWorkingCommand(command, "redo", context(8))).rejects.toThrow("fade failed");
    expect(history.undoStack).toEqual([]);
    expect(history.redoStack).toEqual([command]);
  });

  it("Gain과 Fade command는 하나의 strict LIFO stack에서 교차 이동한다", () => {
    const history = new MemoryCommandHistory();
    const gain = { type: "CLIP_GAIN" as const, clipId: "clip-1", beforeGainDb: "0.00", afterGainDb: "3.00" };
    const fadeA = { type: "CLIP_FADE" as const, clipId: "clip-1", before: { fadeIn: "0", fadeOut: "0" }, after: { fadeIn: "0.5", fadeOut: "0" } };
    const fadeB = { type: "CLIP_FADE" as const, clipId: "clip-1", before: { fadeIn: "0.5", fadeOut: "0" }, after: { fadeIn: "0.5", fadeOut: "0.25" } };
    history.push(fadeA);
    history.push(gain);
    history.push(fadeB);
    expect(history.undoStack.map((item) => item.type)).toEqual(["CLIP_FADE", "CLIP_GAIN", "CLIP_FADE"]);
    history.completeUndo();
    history.completeUndo();
    history.completeUndo();
    expect(history.redoStack.map((item) => item.type)).toEqual(["CLIP_FADE", "CLIP_GAIN", "CLIP_FADE"]);
    history.completeRedo();
    history.completeRedo();
    history.completeRedo();
    expect(history.undoStack).toEqual([fadeA, gain, fadeB]);
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
