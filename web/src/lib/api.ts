import type { Project } from "./types";

/** Client for the AURA engine, via the same-origin rewrite proxy. */

const BASE = "/api/engine";

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`engine ${res.status}`);
  return res.json();
}

export async function createProject(form: {
  brief: string;
  tier?: string;
  files?: File[];
}): Promise<Project> {
  const fd = new FormData();
  fd.set("brief", form.brief);
  fd.set("tier", form.tier ?? "preview");
  for (const f of form.files ?? []) fd.append("files", f);
  const res = await fetch(`${BASE}/projects`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.text()) || `engine ${res.status}`);
  return res.json();
}

export async function answerQuestions(
  id: string,
  answers: Record<string, string>,
  acceptDefaults = false,
): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers, accept_defaults: acceptDefaults }),
  });
  if (!res.ok) throw new Error(`engine ${res.status}`);
  return res.json();
}

export async function pickDesign(id: string, candidateId: string): Promise<void> {
  await fetch(`${BASE}/projects/${id}/pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function fileUrl(projectId: string, artifactId: string): string {
  return `${BASE}/projects/${projectId}/files/${artifactId}`;
}

export function eventsUrl(projectId: string): string {
  return `${BASE}/projects/${projectId}/events`;
}
