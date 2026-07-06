"use client";

/** One project's page: the agent theater while the crew works, the clarify
 * panel when the studio has a question, the gallery reveal when it's done. */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { answerQuestions, getProject } from "@/lib/api";
import type { Project } from "@/lib/types";
import Theater from "@/components/Theater";
import Gallery from "@/components/Gallery";

export default function StudioPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProject(await getProject(id));
    } catch (e) {
      setError(String(e));
    }
  }, [id]);

  useEffect(() => {
    const t = setTimeout(refresh, 0);        // initial load, off the render pass
    const interval = setInterval(refresh, 4000);
    return () => { clearTimeout(t); clearInterval(interval); };
  }, [refresh]);

  if (error) return <Shell><p className="text-crimson">{error}</p></Shell>;
  if (!project) return <Shell><p className="text-ivory-dim">Opening the studio…</p></Shell>;

  return (
    <Shell>
      {project.status === "done" && project.package ? (
        <Gallery project={project} />
      ) : project.status === "failed" ? (
        <div className="text-center">
          <h1 className="font-display text-3xl text-ivory-bright">The studio hit a wall.</h1>
          <p className="mt-3 text-sm text-ivory-dim">
            This run couldn&apos;t finish. You haven&apos;t been charged — start again and
            we&apos;ll take a different route.
          </p>
        </div>
      ) : (
        <>
          <header className="mb-10 text-center">
            <div className="text-[11px] uppercase tracking-[0.35em] text-gold">
              Project {project.project_id}
            </div>
            <h1 className="font-display mt-3 text-4xl text-ivory-bright">
              The studio is working
            </h1>
            <p className="mt-2 text-sm text-ivory-dim">
              Watch the crew. Designs appear the moment they develop.
            </p>
          </header>
          {project.pending_interrupt?.kind === "clarify" && (
            <ClarifyPanel project={project} onAnswered={refresh} />
          )}
          <Theater project={project} />
        </>
      )}
    </Shell>
  );
}

function ClarifyPanel({ project, onAnswered }: { project: Project; onAnswered: () => void }) {
  const questions = (project.pending_interrupt?.payload?.questions ?? []) as {
    question: string; why_it_matters: string; default_assumption: string;
  }[];
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(acceptDefaults: boolean) {
    setBusy(true);
    await answerQuestions(project.project_id, acceptDefaults ? {} : answers, acceptDefaults);
    onAnswered();
  }

  return (
    <div className="mb-10 rounded border border-gold/50 bg-ink-soft p-6">
      <div className="text-[11px] uppercase tracking-[0.3em] text-gold">
        The studio has a question
      </div>
      <div className="mt-4 space-y-5">
        {questions.map((q) => (
          <div key={q.question}>
            <label className="block text-sm text-ivory">{q.question}</label>
            <p className="mt-1 text-xs text-ivory-dim">
              {q.why_it_matters} — otherwise we&apos;ll assume: {q.default_assumption}
            </p>
            <input
              className="mt-2 w-full rounded border border-ivory-dim/30 bg-ink px-3 py-2 text-sm text-ivory outline-none focus:border-gold"
              value={answers[q.question] ?? ""}
              onChange={(e) => setAnswers((a) => ({ ...a, [q.question]: e.target.value }))}
            />
          </div>
        ))}
      </div>
      <div className="mt-5 flex gap-3">
        <button disabled={busy} onClick={() => submit(false)}
                className="rounded bg-gold px-5 py-2 text-sm text-ink transition hover:bg-gold-bright disabled:opacity-50">
          Send answers
        </button>
        <button disabled={busy} onClick={() => submit(true)}
                className="rounded border border-ivory-dim/40 px-5 py-2 text-sm text-ivory-dim transition hover:border-gold disabled:opacity-50">
          Proceed with your assumptions
        </button>
      </div>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-14">
      <nav className="mb-12 flex items-center justify-between">
        <Link href="/" className="font-display text-xl tracking-wide text-ivory-bright">
          AURA <span className="text-gold">Studio</span>
        </Link>
        <Link href="/new" className="text-sm text-ivory-dim transition hover:text-gold-bright">
          New project
        </Link>
      </nav>
      {children}
    </main>
  );
}
