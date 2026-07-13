/** Sample project used in design-review mode and as an offline fallback —
 * real data shapes from the engine, populated with the advocate demo. */

export interface TaskInfo {
  task_id: string;
  role_key: string;
  title: string;
  status: "pending" | "running" | "succeeded" | "failed" | "skipped" | "budget_denied";
}

export interface SelectedCandidate {
  candidate_id: string;
  direction: {
    name: string;
    thesis: string;
    risk_level: "safe" | "balanced" | "bold";
  };
  preview_artifact_ids: string[];
}

export interface Project {
  project_id: string;
  status: "queued" | "running" | "waiting_input" | "waiting_review" | "done" | "failed";
  tier: string;
  paid: boolean;
  tasks: TaskInfo[];
  package: {
    aura: {
      archetype: string;
      essence_statement: string;
      adjectives: string[];
      palette: { primary_hex: string[]; accent_hex: string[] };
    };
    selected: SelectedCandidate[];
    rationales: { candidate_id: string; headline: string; body: string }[];
    rejected_count: number;
  } | null;
}

export const SAMPLE_PROJECT: Project = {
  project_id: "sample",
  status: "done",
  tier: "preview",
  paid: false,
  tasks: [
    { task_id: "type1", role_key: "calligraphy_specialist", title: "Type system", status: "succeeded" },
    { task_id: "motif1", role_key: "motif_illustrator", title: "Signature motifs", status: "succeeded" },
    { task_id: "design1", role_key: "layout_designer", title: "Design: Counsel in Ink", status: "succeeded" },
    { task_id: "design2", role_key: "layout_designer", title: "Design: The Gold Standard", status: "running" },
    { task_id: "design3", role_key: "layout_designer", title: "Design: Brief & Verdict", status: "running" },
    { task_id: "design4", role_key: "layout_designer", title: "Design: Statute Modern", status: "pending" },
  ],
  package: {
    aura: {
      archetype: "The Sage-Advocate: quiet authority earned in court, not announced.",
      essence_statement:
        "Two decades of constitutional practice compressed into stillness. " +
        "The card should feel like his handshake: brief, firm, remembered.",
      adjectives: ["measured", "precise", "formidable", "traditional", "unhurried"],
      palette: { primary_hex: ["#14100c", "#e8ddc8"], accent_hex: ["#b08d4f"] },
    },
    selected: [
      {
        candidate_id: "c1",
        direction: {
          name: "Counsel in Ink",
          thesis: "Quiet authority: letterpress restraint, ivory and iron-gall black.",
          risk_level: "safe",
        },
        preview_artifact_ids: ["sample"],
      },
      {
        candidate_id: "c2",
        direction: {
          name: "The Gold Standard",
          thesis: "Earned gravitas: deep charcoal field, hairline gold rules, small caps.",
          risk_level: "balanced",
        },
        preview_artifact_ids: ["sample"],
      },
      {
        candidate_id: "c3",
        direction: {
          name: "Statute Modern",
          thesis: "Bold subversion: swiss type on legal-pad yellow, for the fearless litigator.",
          risk_level: "bold",
        },
        preview_artifact_ids: ["sample"],
      },
    ],
    rationales: [
      { candidate_id: "c1", headline: "Authority that doesn't raise its voice",
        body: "The card mirrors how you practice: spare, exact, final. Gold appears once — like a citation that ends the argument." },
      { candidate_id: "c2", headline: "Gravitas, measured in hairlines",
        body: "Charcoal carries the weight; the gold rule does the talking. A card for rooms where volume is a weakness." },
      { candidate_id: "c3", headline: "The statement",
        body: "For the days you argue in front of cameras: swiss discipline on legal-pad yellow. Unmistakable in a stack of ivory." },
    ],
    rejected_count: 1,
  },
};

/** Local asset used for sample previews (a real engine render). */
export const SAMPLE_CARD = require("../assets/sample-card.png");
