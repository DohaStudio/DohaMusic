import { create } from "zustand";
import { dohaApi } from "@/services/doha-api";
import type { HistoryItemDto } from "@/types/api";

interface HistoryState {
  items: HistoryItemDto[];
  loading: boolean;
  error?: string;
  query: string;
  status: string;
  setQuery: (query: string) => void;
  setStatus: (status: string) => void;
  load: () => Promise<void>;
}

export const useHistoryStore = create<HistoryState>((set, get) => ({
  items: [],
  loading: false,
  query: "",
  status: "",
  setQuery: (query) => set({ query }),
  setStatus: (status) => set({ status }),
  load: async () => {
    set({ loading: true, error: undefined });
    try {
      const { query, status } = get();
      const items = await dohaApi.getHistory({ q: query || undefined, status: status || undefined });
      set({ items, loading: false });
    } catch {
      set({ loading: false, error: "만든 음악을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." });
    }
  },
}));
