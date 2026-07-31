import { create } from "zustand";
import { dohaApi } from "@/services/doha-api";
import type { ProjectDto } from "@/types/api";

interface ProjectState {
  items: ProjectDto[];
  loading: boolean;
  error?: string;
  load: () => Promise<void>;
  createProject: (title: string, description?: string) => Promise<void>;
  updateProject: (id: string, title: string, description?: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  items: [],
  loading: false,
  load: async () => {
    set({ loading: true, error: undefined });
    try {
      set({ items: await dohaApi.getProjects(), loading: false });
    } catch {
      set({ loading: false, error: "Project를 불러오지 못했습니다." });
    }
  },
  createProject: async (title, description) => {
    await dohaApi.createProject({ title, description });
    await get().load();
  },
  updateProject: async (id, title, description) => {
    await dohaApi.updateProject(id, { title, description: description ?? null });
    await get().load();
  },
  deleteProject: async (id) => {
    await dohaApi.deleteProject(id);
    await get().load();
  },
}));
