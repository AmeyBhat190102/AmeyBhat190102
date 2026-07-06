"use client";

/** Checkout: one decision, no upsell maze. Stripe redirects; Razorpay uses
 * its widget; local dev unlocks instantly so the loop is demoable. */

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";

export default function Checkout() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId: id, plan: "unlock" }),
      });
      const session = await res.json();
      if (!res.ok) throw new Error(session.error ?? "checkout failed");
      if (session.redirectUrl) {
        window.location.href = session.redirectUrl;
      } else if (session.unlocked) {
        router.push(`/studio/${id}?paid=1`);
      } else if (session.razorpayOrder) {
        // Razorpay's browser widget flow; loaded on demand.
        setError("Razorpay widget flow: complete payment in the popup.");
      }
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-lg flex-1 px-6 py-20 text-center">
      <a href={`/studio/${id}`} className="text-sm text-ivory-dim hover:text-ivory">
        ← Back to your gallery
      </a>
      <h1 className="font-display mt-8 text-4xl text-ivory-bright">Take it home</h1>
      <div className="mt-8 rounded border border-gold/40 bg-ink-soft p-8 text-left">
        <div className="flex items-baseline justify-between">
          <span className="font-display text-xl text-ivory-bright">Project unlock</span>
          <span className="text-lg text-gold-bright">$29 · ₹999</span>
        </div>
        <ul className="mt-5 space-y-2 text-sm text-ivory-dim">
          <li>· Print-ready PDFs at true physical size</li>
          <li>· Full-resolution previews, unwatermarked</li>
          <li>· Design source files — editable forever</li>
          <li>· 2 revision rounds with the studio</li>
        </ul>
        <button onClick={pay} disabled={busy}
                className="mt-7 w-full rounded bg-gold px-6 py-3 text-sm font-medium tracking-wide text-ink transition hover:bg-gold-bright disabled:opacity-60">
          {busy ? "Opening payment…" : "Pay & unlock"}
        </button>
        {error && <p className="mt-3 text-sm text-crimson">{error}</p>}
        <p className="mt-4 text-center text-[11px] text-ivory-dim/70">
          Stripe worldwide · Razorpay (UPI/cards) in India
        </p>
      </div>
    </main>
  );
}
