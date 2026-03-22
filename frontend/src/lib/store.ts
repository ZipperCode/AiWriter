import { create } from "zustand";

interface AppState {
  currentProjectId: string | null;
  sidebarOpen: boolean;
  setCurrentProject: (id: string | null) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentProjectId: null,
  sidebarOpen: true,
  setCurrentProject: (id) => set({ currentProjectId: id }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
