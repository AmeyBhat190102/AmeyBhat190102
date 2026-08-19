/** Mirrors of the engine's contracts (aura-studio/src/aura). Keep in sync;
 * packages/contracts generation replaces this by codegen later. */

export type ProjectStatus =
  | "queued" | "running" | "waiting_input" | "waiting_review"
  | "done" | "failed" | "cancelled";

export interface TaskInfo {
  task_id: string;
  role_key: string;
  title: string;
  status: "pending" | "running" | "succeeded" | "failed" | "skipped" | "budget_denied";
  depends_on: string[];
  cost_usd: number;
}

export interface RationaleCard {
  candidate_id: string;
  headline: string;
  body: string;
}

export interface SelectedCandidate {
  candidate_id: string;
  direction: {
    name: string;
    thesis: string;
    how_it_expresses_aura: string;
    risk_level: "safe" | "balanced" | "bold";
  };
  revision: number;
  preview_artifact_ids: string[];
  print_artifact_id: string | null;
}

export interface Project {
  project_id: string;
  status: ProjectStatus;
  tier: "preview" | "standard" | "studio";
  paid: boolean;
  brief: Record<string, unknown> | null;
  plan: { rationale: string; tasks: TaskInfo[] } | null;
  package: {
    aura: { archetype: string; essence_statement: string; adjectives: string[];
            palette: { primary_hex: string[]; accent_hex: string[] } };
    selected: SelectedCandidate[];
    rationales: RationaleCard[];
    rejected_count: number;
  } | null;
  tasks: TaskInfo[];
  pending_interrupt: { kind: string; payload: Record<string, unknown> } | null;
  spent_usd: number;
  error: string | null;
}

export interface StudioEvent {
  id?: number;
  type: string;
  task_id?: string | null;
  role_key?: string | null;
  payload: Record<string, unknown>;
}
