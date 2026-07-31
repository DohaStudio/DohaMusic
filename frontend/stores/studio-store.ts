import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LyricsValidationDto } from "@/types/api";
import type { StudioStep } from "@/types/domain";
import type { KPopPresetId } from "@/features/studio/kpop-presets";

interface StudioDraft {
  currentStep: StudioStep;
  kpopPresetId: KPopPresetId;
  prompt: string;
  genre: string;
  customGenre: string;
  selectedMoods: string[];
  durationPreset: "preview" | "verse" | "custom";
  advancedSettingsOpen: boolean;
  durationSeconds: number;
  seed?: number;
  lyricsMode: "generate" | "write";
  lyricsDocumentId?: string;
  lyricsText: string;
  lyricsValidation?: LyricsValidationDto;
  voiceProfileId: string;
  voiceProfileName?: string;
  pipelineJobId?: string;
}
interface StudioActions {
  patch: (draft: Partial<StudioDraft>) => void;
  setStep: (step: StudioStep) => void;
  reset: () => void;
}
const initial: StudioDraft = {
  currentStep: "settings",
  kpopPresetId: "kpop_dance",
  prompt: "",
  genre: "",
  customGenre: "",
  selectedMoods: [],
  durationPreset: "preview",
  advancedSettingsOpen: false,
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
        kpopPresetId: state.kpopPresetId,
        prompt: state.prompt,
        genre: state.genre,
        customGenre: state.customGenre,
        selectedMoods: state.selectedMoods,
        durationPreset: state.durationPreset,
        advancedSettingsOpen: state.advancedSettingsOpen,
        durationSeconds: state.durationSeconds,
        seed: state.seed,
        lyricsMode: state.lyricsMode,
        lyricsDocumentId: state.lyricsDocumentId,
        lyricsText: state.lyricsText,
        lyricsValidation: state.lyricsValidation,
        voiceProfileId: state.voiceProfileId,
        voiceProfileName: state.voiceProfileName,
        pipelineJobId: state.pipelineJobId,
      }),
    },
  ),
);
