import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_TOKEN = process.env.NEXT_PUBLIC_AUTH_TOKEN || "";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    Authorization: `Bearer ${AUTH_TOKEN}`,
    "Content-Type": "application/json",
  },
});

// Types
export interface Project {
  id: string;
  title: string;
  genre: string;
  status: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Volume {
  id: string;
  project_id: string;
  title: string;
  objective: string;
  sort_order: number;
}

export interface Chapter {
  id: string;
  project_id: string;
  volume_id: string;
  title: string;
  sort_order: number;
  status: string;
  summary: string | null;
  pov_character_id: string | null;
}

export interface Entity {
  id: string;
  project_id: string;
  name: string;
  entity_type: string;
  description: string | null;
  attributes: Record<string, unknown>;
}

export interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  description: string | null;
}

export interface PacingAnalysis {
  chapter_pacing: Array<{
    chapter_id: string;
    strand: string;
    emotion_level: number;
  }>;
  strand_ratios: Record<string, number>;
  avg_quest_ratio: number;
}

// API functions
export const projectsApi = {
  list: () => api.get<Project[]>("/api/projects").then((r) => r.data),
  get: (id: string) => api.get<Project>(`/api/projects/${id}`).then((r) => r.data),
};

export const volumesApi = {
  list: (projectId: string) =>
    api.get<Volume[]>(`/api/projects/${projectId}/volumes`).then((r) => r.data),
};

export const chaptersApi = {
  list: (projectId: string) =>
    api.get<Chapter[]>(`/api/projects/${projectId}/chapters`).then((r) => r.data),
  get: (id: string) => api.get<Chapter>(`/api/chapters/${id}`).then((r) => r.data),
};

export const entitiesApi = {
  list: (projectId: string) =>
    api.get<Entity[]>(`/api/projects/${projectId}/entities`).then((r) => r.data),
  relationships: (projectId: string) =>
    api.get<Relationship[]>(`/api/projects/${projectId}/entities/relationships`).then((r) => r.data),
};

export const pipelineApi = {
  run: (chapterId: string) =>
    api.post("/api/pipeline/run", { chapter_id: chapterId }).then((r) => r.data),
};

export const auditApi = {
  dimensions: () =>
    api.get<{ dimensions: Array<{ id: number; name: string; zh_name: string; category: string; is_deterministic: boolean }>; total: number }>("/api/audit/dimensions").then((r) => r.data),
};

export const pacingApi = {
  analysis: (projectId: string) =>
    api.get<PacingAnalysis>(`/api/projects/${projectId}/pacing`).then((r) => r.data),
};
