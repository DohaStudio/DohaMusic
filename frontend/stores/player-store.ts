import { create } from "zustand";
import type { SafePipelineFile } from "@/types/domain";

interface PlayerState {
  currentFile?: SafePipelineFile;
  shouldPlay: boolean;
  select: (file: SafePipelineFile) => void;
  play: (file: SafePipelineFile) => void;
  pause: () => void;
  reset: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  shouldPlay: false,
  select: (currentFile) => set({ currentFile, shouldPlay: false }),
  play: (currentFile) => set({ currentFile, shouldPlay: true }),
  pause: () => set({ shouldPlay: false }),
  reset: () => set({ currentFile: undefined, shouldPlay: false }),
}));
