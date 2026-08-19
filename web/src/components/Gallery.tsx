"use client";

/** The reveal: designs presented like a gallery opening — one wall, each
 * piece with its rationale read alongside. Watermark-free previews unlock
 * with payment. */

import { useState } from "react";
import { fileUrl, pickDesign } from "@/lib/api";
import type { Project, SelectedCandidate } from "@/lib/types";

const RISK_LABEL: Record<string, string> = {
  safe: "The banker",
  balanced: "The considered choice",
  bold: "The statement",
};

export default function Gallery({ project }: { project: Project }) {
  const [picked, setPicked] = useState<string | null>(null);
  const pkg = project.package;
  if (!pkg) return null;
  const rationaleBy = Object.fromEntries(pkg.rationales.map((r) => [r.candidate_id, r]));

  async function onPick(candidateId: string) {
    setPicked(candidateId);
    await pickDesign(project.project_id, candidateId);
  }

  return (
    <div>
      <header className="text-center">
        <div className="text-[11px] uppercase tracking-[0.35em] text-gold">Your gallery</div>
        <h1 className="font-display mt-3 text-4xl text-ivory-bright">
          {pkg.selected.length} designs. One is unmistakably you.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-ivory-dim">
          {pkg.aura.essence_statement}
        </p>
        <div className="gold-rule mx-auto mt-6 w-40" />
      </header>

      <div className="mt-12 space-y-16">
        {pkg.selected.map((c, i) => (
          <Piece key={c.candidate_id} project={project} c={c}
                 rationale={rationaleBy[c.candidate_id]}
                 index={i} picked={picked === c.candidate_id}
                 onPick={() => onPick(c.candidate_id)} />
        ))}
      </div>

      {!project.paid && (
        <div className="mt-16 rounded border border-gold/40 bg-ink-soft p-8 text-center">
          <h2 className="font-display text-2xl text-ivory-bright">Take it home</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ivory-dim">
            Unlock print-ready PDFs with true physical dimensions, full-resolution
            files, and the design source — yours forever, revisable on request.
          </p>
          <a href={`/checkout/${project.project_id}`}
             className="mt-6 inline-block rounded bg-gold px-8 py-3 text-sm font-medium tracking-wide text-ink transition hover:bg-gold-bright">
            Unlock this project
          </a>
        </div>
      )}
    </div>
  );
}

function Piece({ project, c, rationale, index, picked, onPick }: {
  project: Project;
  c: SelectedCandidate;
  rationale?: { headline: string; body: string };
  index: number;
  picked: boolean;
  onPick: () => void;
}) {
  const flip = index % 2 === 1;
  return (
    <article className={`grid items-center gap-8 lg:grid-cols-2 ${flip ? "lg:[direction:rtl]" : ""}`}>
      <div className="[direction:ltr]">
        {c.preview_artifact_ids.map((id) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={id} src={fileUrl(project.project_id, id)}
               alt={c.direction.name}
               className="develop w-full rounded shadow-[0_20px_60px_rgba(0,0,0,0.55)]" />
        ))}
      </div>
      <div className="[direction:ltr]">
        <div className="text-[10px] uppercase tracking-[0.3em] text-gold">
          {RISK_LABEL[c.direction.risk_level] ?? c.direction.risk_level}
        </div>
        <h3 className="font-display mt-2 text-3xl text-ivory-bright">{c.direction.name}</h3>
        {rationale && (
          <>
            <p className="mt-4 text-lg leading-relaxed text-ivory">{rationale.headline}</p>
            <p className="mt-2 text-sm leading-relaxed text-ivory-dim">{rationale.body}</p>
          </>
        )}
        <p className="mt-4 text-xs leading-relaxed text-ivory-dim/70">{c.direction.thesis}</p>
        <button onClick={onPick}
                className={`mt-6 rounded border px-5 py-2 text-sm transition ${
                  picked
                    ? "border-gold bg-gold text-ink"
                    : "border-ivory-dim/40 text-ivory hover:border-gold hover:text-gold-bright"
                }`}>
          {picked ? "Your choice ✓" : "This is the one"}
        </button>
      </div>
    </article>
  );
}
