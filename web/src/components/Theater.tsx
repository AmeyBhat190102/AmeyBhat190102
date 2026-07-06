"use client";

/** The agent theater: a live window into the studio while the crew works.
 * Renders straight from the engine's SSE event stream — supervisor notes,
 * specialists spawning, thumbnails developing like polaroids. */

import { useEffect, useMemo, useRef, useState } from "react";
import { eventsUrl } from "@/lib/api";
import type { Project, StudioEvent } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  layout_designer: "Layout typographer",
  cover_artist: "Cover artist",
  cinematographer: "Cinematographer",
  copywriter: "Copywriter",
  calligraphy_specialist: "Type specialist",
  motif_illustrator: "Motif illustrator",
  sound_brief_writer: "Sound director",
  logo_designer: "Logo designer",
  critic: "The critic",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "text-ivory-dim/50 border-ivory-dim/20",
  running: "text-gold-bright border-gold animate-pulse",
  succeeded: "text-ivory border-ivory-dim/40",
  failed: "text-crimson border-crimson/60",
  skipped: "text-ivory-dim/40 border-ivory-dim/20 line-through",
  budget_denied: "text-ivory-dim/40 border-ivory-dim/20 line-through",
};

interface CrewTask {
  task_id: string;
  role_key: string;
  title: string;
  status: string;
}

export default function Theater({ project }: { project: Project }) {
  const [events, setEvents] = useState<StudioEvent[]>([]);
  const [crew, setCrew] = useState<Record<string, CrewTask>>({});
  const [aura, setAura] = useState<{ archetype?: string; palette?: string[] }>({});
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = new EventSource(eventsUrl(project.project_id));
    const handle = (e: MessageEvent) => {
      const data: StudioEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev.slice(-120), data]);
      if (data.type === "plan_created") {
        const tasks = (data.payload.tasks ?? []) as CrewTask[];
        setCrew(Object.fromEntries(tasks.map((t) => [t.task_id, { ...t, status: "pending" }])));
      }
      if (data.type === "task_started" && data.task_id) {
        setCrew((c) => ({
          ...c,
          [data.task_id!]: {
            task_id: data.task_id!,
            role_key: data.role_key ?? "",
            title: (data.payload.title as string) ?? c[data.task_id!]?.title ?? "",
            status: "running",
          },
        }));
      }
      if (data.type === "task_finished" && data.task_id) {
        setCrew((c) => ({
          ...c,
          [data.task_id!]: { ...c[data.task_id!], status: (data.payload.status as string) ?? "succeeded" },
        }));
      }
      if (data.type === "aura_ready") {
        setAura({
          archetype: data.payload.archetype as string,
          palette: data.payload.palette as string[],
        });
      }
    };
    // The engine names SSE events by type; listen to all of them.
    for (const t of [
      "status_changed", "brief_ready", "aura_ready", "plan_created", "task_started",
      "task_progress", "artifact_ready", "task_finished", "critique",
      "revision_started", "interrupt_raised", "interrupt_resolved", "budget_update",
      "package_ready", "error",
    ]) {
      source.addEventListener(t, handle);
    }
    return () => source.close();
  }, [project.project_id]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [events]);

  const narration = useMemo(() => events.filter((e) =>
    ["brief_ready", "aura_ready", "plan_created", "critique", "revision_started",
     "artifact_ready", "package_ready"].includes(e.type)), [events]);

  return (
    <div className="grid gap-8 lg:grid-cols-[1.1fr_1fr]">
      {/* The crew board */}
      <section>
        <h2 className="font-display text-2xl text-ivory-bright">The crew</h2>
        <p className="mt-1 text-sm text-ivory-dim">
          Cast for this brief by the producer — specialists spawn as their inputs arrive.
        </p>
        {aura.archetype && (
          <div className="mt-4 rounded border border-gold/30 bg-ink-soft p-4 develop">
            <div className="text-[11px] uppercase tracking-[0.3em] text-gold">Aura reading</div>
            <div className="font-display mt-2 text-lg text-ivory-bright">{aura.archetype}</div>
            {aura.palette && (
              <div className="mt-3 flex gap-2">
                {aura.palette.map((hex) => (
                  <span key={hex} className="h-5 w-5 rounded-full border border-ivory-dim/30"
                        style={{ background: hex }} title={hex} />
                ))}
              </div>
            )}
          </div>
        )}
        <ul className="mt-5 space-y-3">
          {Object.values(crew).map((t) => (
            <li key={t.task_id}
                className={`rounded border bg-ink-soft px-4 py-3 transition-colors ${STATUS_STYLES[t.status] ?? ""}`}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium">
                  {ROLE_LABELS[t.role_key] ?? t.role_key}
                </span>
                <span className="text-[11px] uppercase tracking-widest opacity-70">
                  {t.status.replace("_", " ")}
                </span>
              </div>
              <div className="mt-1 text-xs opacity-70">{t.title}</div>
            </li>
          ))}
          {Object.keys(crew).length === 0 && (
            <li className="rounded border border-ivory-dim/20 bg-ink-soft px-4 py-6 text-sm text-ivory-dim">
              Reading your brief, extracting the aura, casting the crew…
            </li>
          )}
        </ul>
      </section>

      {/* Narration feed */}
      <section className="min-w-0">
        <h2 className="font-display text-2xl text-ivory-bright">From the floor</h2>
        <div ref={feedRef}
             className="mt-4 max-h-[32rem] space-y-3 overflow-y-auto rounded border border-ivory-dim/15 bg-ink-soft p-4">
          {narration.map((e, i) => <Narration key={`${e.id ?? i}-${i}`} e={e} />)}
          {narration.length === 0 && (
            <div className="text-sm text-ivory-dim">The studio lights are on…</div>
          )}
        </div>
      </section>
    </div>
  );
}

function Narration({ e }: { e: StudioEvent }) {
  const p = e.payload;
  switch (e.type) {
    case "brief_ready":
      return <Line tag="Intake">Brief understood — {String(p.artifact_type ?? "artifact")} for {String(p.subject ?? "the client")}.</Line>;
    case "aura_ready":
      return <Line tag="Aura">{String(p.archetype ?? "")}</Line>;
    case "plan_created":
      return <Line tag="Producer">{String(p.rationale ?? "Crew cast.")}</Line>;
    case "artifact_ready":
      return <Line tag="Studio">A {String(p.kind ?? "render")} just developed{p.direction ? <> — <em>{String(p.direction)}</em></> : null}.</Line>;
    case "critique":
      return (
        <Line tag="Critic">
          {String(p.verdict) === "ship" ? "Approved" : String(p.verdict) === "revise" ? "Sent back" : "Killed"}
          {typeof p.overall === "number" ? ` at ${(p.overall as number).toFixed(1)}/10` : ""}.
          {Array.isArray(p.notes) && p.notes.length > 0 ? ` “${p.notes[0]}”` : ""}
        </Line>
      );
    case "revision_started":
      return <Line tag="Studio">Revision underway on <em>{String(p.direction ?? "a design")}</em>.</Line>;
    case "package_ready":
      return <Line tag="Curator">Gallery assembled — {String(p.selected)} designs made the wall, {String(p.rejected)} did not.</Line>;
    default:
      return null;
  }
}

function Line({ tag, children }: { tag: string; children: React.ReactNode }) {
  return (
    <div className="text-sm leading-relaxed develop">
      <span className="mr-2 text-[10px] uppercase tracking-[0.25em] text-gold">{tag}</span>
      <span className="text-ivory/90">{children}</span>
    </div>
  );
}
