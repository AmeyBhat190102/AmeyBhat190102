"use client";

/** The brief wizard: conversational, one thing per screen, ends with the
 * handoff into the theater. The studio's first impression — unhurried. */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createProject } from "@/lib/api";

const ARTIFACTS = [
  { key: "business card", label: "Business card", hint: "authority you can hand over" },
  { key: "wedding invitation", label: "Wedding invitation", hint: "a family's occasion, held" },
  { key: "book cover", label: "Book cover", hint: "the argument before page one" },
  { key: "poster", label: "Poster", hint: "one idea at wall scale" },
  { key: "product video", label: "Product film", hint: "8 seconds of presence" },
  { key: "brand kit", label: "Something else", hint: "tell us in your words" },
];

export default function NewProject() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [artifact, setArtifact] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [facts, setFacts] = useState("");
  const [feel, setFeel] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    const brief = [
      `I need a ${artifact}.`,
      `About the subject: ${subject}`,
      facts && `Facts that must appear exactly as written: ${facts}`,
      feel && `How it should feel: ${feel}`,
    ].filter(Boolean).join("\n\n");
    try {
      const project = await createProject({ brief, files });
      router.push(`/studio/${project.project_id}`);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  const steps = [
    <div key="artifact">
      <StepTitle n={1}>What are we making?</StepTitle>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {ARTIFACTS.map((a) => (
          <button key={a.key}
                  onClick={() => { setArtifact(a.key); setStep(1); }}
                  className={`rounded border p-5 text-left transition ${
                    artifact === a.key
                      ? "border-gold bg-ink-soft"
                      : "border-ivory-dim/20 bg-ink-soft/50 hover:border-gold/60"
                  }`}>
            <div className="font-display text-xl text-ivory-bright">{a.label}</div>
            <div className="mt-1 text-xs text-ivory-dim">{a.hint}</div>
          </button>
        ))}
      </div>
    </div>,

    <div key="subject">
      <StepTitle n={2}>Who — or what — is this for?</StepTitle>
      <p className="mt-2 text-sm text-ivory-dim">
        Don&apos;t describe the design. Describe the person, the product, the occasion —
        what they do, how long they&apos;ve done it, how people feel around them. We
        translate presence; give us presence to translate.
      </p>
      <textarea value={subject} onChange={(e) => setSubject(e.target.value)}
                rows={6} autoFocus
                placeholder="e.g. My father, a senior advocate — 20 years in constitutional law. Measured, precise. Judges lean in when he speaks quietly…"
                className="mt-6 w-full rounded border border-ivory-dim/30 bg-ink-soft p-4 text-sm leading-relaxed text-ivory outline-none focus:border-gold" />
      <NavButtons onBack={() => setStep(0)} onNext={() => setStep(2)}
                  nextDisabled={subject.trim().length < 20} />
    </div>,

    <div key="facts">
      <StepTitle n={3}>What must appear, letter for letter?</StepTitle>
      <p className="mt-2 text-sm text-ivory-dim">
        Names, titles, phone numbers, dates, venues. We print these verbatim — our
        critic rejects any design that gets a character wrong.
      </p>
      <textarea value={facts} onChange={(e) => setFacts(e.target.value)}
                rows={4} autoFocus
                placeholder={"Adv. R. K. Sharma\nAdvocate, High Court\n+91 98765 43210 · rks@chambers.law"}
                className="mt-6 w-full rounded border border-ivory-dim/30 bg-ink-soft p-4 text-sm leading-relaxed text-ivory outline-none focus:border-gold" />
      <NavButtons onBack={() => setStep(1)} onNext={() => setStep(3)} />
    </div>,

    <div key="feel">
      <StepTitle n={4}>Anything it must feel like — or never be?</StepTitle>
      <p className="mt-2 text-sm text-ivory-dim">
        Optional. Preferences, traditions to honor, things you&apos;ve seen and hated.
      </p>
      <textarea value={feel} onChange={(e) => setFeel(e.target.value)}
                rows={3}
                placeholder="Understated. Premium paper. Absolutely no clip-art scales of justice."
                className="mt-6 w-full rounded border border-ivory-dim/30 bg-ink-soft p-4 text-sm leading-relaxed text-ivory outline-none focus:border-gold" />
      <div className="mt-6">
        <label className="block text-sm text-ivory">
          Photos help us read the aura <span className="text-ivory-dim">(portrait, product, past materials — optional)</span>
        </label>
        <input type="file" multiple accept="image/*"
               onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
               className="mt-3 block w-full text-sm text-ivory-dim file:mr-4 file:rounded file:border file:border-gold/60 file:bg-transparent file:px-4 file:py-2 file:text-sm file:text-gold-bright hover:file:border-gold" />
      </div>
      {error && <p className="mt-4 text-sm text-crimson">{error}</p>}
      <div className="mt-8 flex items-center gap-4">
        <button onClick={() => setStep(2)} className="text-sm text-ivory-dim hover:text-ivory">← Back</button>
        <button onClick={submit} disabled={busy}
                className="rounded bg-gold px-8 py-3 text-sm font-medium tracking-wide text-ink transition hover:bg-gold-bright disabled:opacity-60">
          {busy ? "Reading your aura…" : "Open the studio"}
        </button>
      </div>
    </div>,
  ];

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-14">
      <nav className="mb-14">
        <Link href="/" className="font-display text-xl tracking-wide text-ivory-bright">
          AURA <span className="text-gold">Studio</span>
        </Link>
      </nav>
      {steps[step]}
    </main>
  );
}

function StepTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.35em] text-gold">Step {n} of 4</div>
      <h1 className="font-display mt-3 text-3xl text-ivory-bright">{children}</h1>
    </div>
  );
}

function NavButtons({ onBack, onNext, nextDisabled }: {
  onBack: () => void; onNext: () => void; nextDisabled?: boolean;
}) {
  return (
    <div className="mt-8 flex items-center gap-4">
      <button onClick={onBack} className="text-sm text-ivory-dim hover:text-ivory">← Back</button>
      <button onClick={onNext} disabled={nextDisabled}
              className="rounded border border-gold px-6 py-2.5 text-sm text-gold-bright transition hover:bg-gold hover:text-ink disabled:opacity-40">
        Continue
      </button>
    </div>
  );
}
