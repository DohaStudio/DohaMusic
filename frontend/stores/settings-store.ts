import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface SettingsState {
  reducedMotion: boolean | null;
  onboardingCompleted: boolean;
  onboardingOpen: boolean;
  setReducedMotion: (value: boolean | null) => void;
  completeOnboarding: () => void;
  reopenOnboarding: () => void;
  reset: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      reducedMotion: null,
      onboardingCompleted: false,
      onboardingOpen: true,
      setReducedMotion: (reducedMotion) => set({ reducedMotion }),
      completeOnboarding: () => set({ onboardingCompleted: true, onboardingOpen: false }),
      reopenOnboarding: () =>
        set({ onboardingCompleted: false, onboardingOpen: true }),
      reset: () => set({ reducedMotion: null, onboardingCompleted: false, onboardingOpen: true }),
    }),
    {
      name: "doha-studio-settings",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ reducedMotion: state.reducedMotion, onboardingCompleted: state.onboardingCompleted }),
    },
  ),
);
