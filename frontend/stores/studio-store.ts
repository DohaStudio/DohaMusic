import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LyricsValidationDto } from "@/types/api";
import type { StudioStep } from "@/types/domain";

interface StudioDraft {
  currentStep: StudioStep;
  prompt: string;
  genre: string;
  durationSeconds: number;
  seed?: number;
  lyricsMode: "generate" | "write";
  lyricsDocumentId?: string;
  lyricsText: string;
  lyricsValidation?: LyricsValidationDto;
  voiceProfileId: string;
  pipelineJobId?: string;
}
interface StudioActions {
  patch: (draft: Partial<StudioDraft>) => void;
  setStep: (step: StudioStep) => void;
  reset: () => void;
}
const initial: StudioDraft = {
  currentStep: "settings",
  prompt: "",
  genre: "R&B",
  durationSeconds: 30,
  lyricsMode: "generate",
  lyricsText: "",
  voiceProfileId: "",
};

export const useStudioStore = create<StudioDraft & StudioActions>()(
  persist(
    (set) => ({
      ...initial,
      patch: (draft) => set(draft),
      setStep: (currentStep) => set({ currentStep }),
      reset: () => set(initial),
    }),
    {
      name: "doha-studio-draft",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        currentStep: state.currentStep,
        prompt: state.prompt,
        genre: state.genre,
        durationSeconds: state.durationSeconds,
        seed: state.seed,
        lyricsMode: state.lyricsMode,
        lyricsDocumentId: state.lyricsDocumentId,
        lyricsText: state.lyricsText,
        lyricsValidation: state.lyricsValidation,
        voiceProfileId: state.voiceProfileId,
        pipelineJobId: state.pipelineJobId,
      }),
    },
  ),
);
