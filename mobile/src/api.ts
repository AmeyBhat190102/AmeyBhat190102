/** Engine client — same REST surface the web app proxies
 * (aura-studio/src/aura/api/main.py). In design-review mode (or when the
 * engine is unreachable) screens fall back to SAMPLE data so the full UI
 * renders for visual review without infrastructure. */

import { Project, SAMPLE_PROJECT } from "./sample";

const BASE = process.env.EXPO_PUBLIC_ENGINE_URL ?? "http://localhost:8800";
export const DESIGN_REVIEW = process.env.EXPO_PUBLIC_DESIGN_REVIEW === "1";

export async function getProject(id: string): Promise<Project> {
  if (DESIGN_REVIEW) return { ...SAMPLE_PROJECT, project_id: id };
  try {
    const res = await fetch(`${BASE}/projects/${id}`);
    if (!res.ok) throw new Error(`engine ${res.status}`);
    return await res.json();
  } catch (e) {
    if (id === SAMPLE_PROJECT.project_id) return SAMPLE_PROJECT;
    throw e;
  }
}

export async function createProject(brief: string): Promise<Project> {
  if (DESIGN_REVIEW) return SAMPLE_PROJECT;
  const fd = new FormData();
  fd.append("brief", brief);
  fd.append("tier", "preview");
  const res = await fetch(`${BASE}/projects`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.text()) || `engine ${res.status}`);
  return res.json();
}

export function fileUrl(projectId: string, artifactId: string): string {
  return `${BASE}/projects/${projectId}/files/${artifactId}`;
}

export type { Project };
