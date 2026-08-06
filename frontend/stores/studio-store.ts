import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LyricsValidationDto } from "@/types/api";
import type { StudioStep } from "@/types/domain";
import {
  createDefaultKPopGenerationOptions,
  type KPopGenerationOptions,
  type KPopPresetId,
} from "@/features/studio/kpop-presets";

interface StudioDraft {
  currentStep: StudioStep;
  kpopPresetId: KPopPresetId;
  generationOptions: KPopGenerationOptions;
  generationOptionsCustomized: boolean;
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
  selectKPopPreset: (presetId: KPopPresetId) => void;
  updateGenerationOptions: (draft: Partial<KPopGenerationOptions>) => void;
  resetGenerationOptions: () => void;
}
const initial: StudioDraft = {
  currentStep: "settings",
  kpopPresetId: "kpop_dance",
  generationOptions: createDefaultKPopGenerationOptions("kpop_dance"),
  generationOptionsCustomized: false,
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
    (set, get) => ({
      ...initial,
      patch: (draft) => set(draft),
      setStep: (currentStep) => set({ currentStep }),
      reset: () => set(initial),
      selectKPopPreset: (kpopPresetId) => {
        const state = get();
        set({
          kpopPresetId,
          generationOptions: state.generationOptionsCustomized
            ? { ...state.generationOptions, presetId: kpopPresetId }
            : createDefaultKPopGenerationOptions(kpopPresetId),
        });
      },
      updateGenerationOptions: (draft) => set((state) => ({
        generationOptions: { ...state.generationOptions, ...draft, presetId: state.kpopPresetId },
        generationOptionsCustomized: true,
      })),
      resetGenerationOptions: () => set((state) => ({
        generationOptions: createDefaultKPopGenerationOptions(state.kpopPresetId),
        generationOptionsCustomized: false,
      })),
    }),
    {
      name: "doha-studio-draft",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        currentStep: state.currentStep,
        kpopPresetId: state.kpopPresetId,
        generationOptions: state.generationOptions,
        generationOptionsCustomized: state.generationOptionsCustomized,
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
      version: 1,
      migrate: (persisted) => {
        const state = (persisted ?? {}) as Partial<StudioDraft>;
        const presetId = state.kpopPresetId ?? "kpop_dance";
        return {
          ...state,
          kpopPresetId: presetId,
          generationOptions: state.generationOptions ?? createDefaultKPopGenerationOptions(presetId),
          generationOptionsCustomized: state.generationOptionsCustomized ?? false,
        };
      },
    },
  ),
);
