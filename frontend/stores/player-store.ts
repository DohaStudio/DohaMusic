import { create } from "zustand";
import type { SafePipelineFile } from "@/types/domain";

interface PlayerState {
  currentFile?: SafePipelineFile;
  shouldPlay: boolean;
  currentTime: number;
  duration: number;
  loading: boolean;
  error: string;
  seekRevision: number;
  select: (file: SafePipelineFile) => void;
  play: (file: SafePipelineFile) => void;
  pause: () => void;
  seek: (time: number) => void;
  syncCurrentTime: (time: number) => void;
  syncDuration: (duration: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
  reset: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  shouldPlay: false,
  currentTime: 0,
  duration: 0,
  loading: false,
  error: "",
  seekRevision: 0,
  select: (currentFile) => set((state) => (
    state.currentFile?.id === currentFile.id
      ? { currentFile }
      : {
          currentFile,
          shouldPlay: false,
          currentTime: 0,
          duration: 0,
          loading: false,
          error: "",
        }
  )),
  play: (currentFile) => set((state) => (
    state.currentFile?.id === currentFile.id
      ? { shouldPlay: true, error: "" }
      : {
          currentFile,
          shouldPlay: true,
          currentTime: 0,
          duration: 0,
          loading: false,
          error: "",
        }
  )),
  pause: () => set({ shouldPlay: false }),
  seek: (currentTime) => set((state) => ({
    currentTime,
    seekRevision: state.seekRevision + 1,
  })),
  syncCurrentTime: (currentTime) => set({ currentTime }),
  syncDuration: (duration) => set({ duration }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set({
    currentFile: undefined,
    shouldPlay: false,
    currentTime: 0,
    duration: 0,
    loading: false,
    error: "",
    seekRevision: 0,
  }),
}));
