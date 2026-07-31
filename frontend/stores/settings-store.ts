import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface SettingsState {
  reducedMotion: boolean | null;
  setReducedMotion: (value: boolean | null) => void;
  reset: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      reducedMotion: null,
      setReducedMotion: (reducedMotion) => set({ reducedMotion }),
      reset: () => set({ reducedMotion: null }),
    }),
    {
      name: "doha-studio-settings",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ reducedMotion: state.reducedMotion }),
    },
  ),
);
