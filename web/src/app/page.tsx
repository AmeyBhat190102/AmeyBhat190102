/** The Glass Studio: the site is a working design studio you can see into.
 * Server component — fast, static, type-led. */

const CRAFT = [
  {
    title: "We read, before we draw",
    body: "A dedicated aura agent studies who you are — your words, your photographs, your standing — and writes the visual constitution every designer must obey: typefaces, palette, materials, and the clichés forbidden in your name.",
  },
  {
    title: "A crew is cast for your brief alone",
    body: "No fixed pipeline. A producer agent hires the specialists your project needs — a copywriter for a wedding's wording, a cinematographer for a product film, a motif illustrator when a symbol should mean something — and they work in parallel, live, in front of you.",
  },
  {
    title: "Type is engineered, never hallucinated",
    body: "Your name, number and dates are typeset by a deterministic layout engine at true physical size — print-grade PDFs a press accepts. Image models paint beneath the type; they never touch your letters.",
  },
  {
    title: "A critic stands at the door",
    body: "Every design faces a vision critic scoring aura fidelity, craft, legibility and print safety. Weak work goes back to its designer with notes. What reaches your gallery survived judgment.",
  },
];

const PRICING = [
  {
    name: "Preview", price: "Free",
    features: ["Full studio run", "Watch the crew live", "Watermarked previews"],
    cta: "Start a project", href: "/new", featured: false,
  },
  {
    name: "Standard", price: "$29 · ₹999",
    features: ["4–5 finished designs", "Print-ready PDF + full-res files", "2 revision rounds", "Design rationale for each piece"],
    cta: "Start a project", href: "/new", featured: true,
  },
  {
    name: "Studio", price: "$99 · ₹4,999",
    features: ["More concept territories", "Premium render models", "A human editor reviews before you see it", "5 revision rounds"],
    cta: "Start a project", href: "/new", featured: false,
  },
];

export default function Landing() {
  return (
    <main className="flex-1">
      {/* Nav */}
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-8">
        <span className="font-display text-xl tracking-wide text-ivory-bright">
          AURA <span className="text-gold">Studio</span>
        </span>
        <div className="flex items-center gap-6 text-sm text-ivory-dim">
          <a href="#craft" className="transition hover:text-gold-bright">The craft</a>
          <a href="#pricing" className="transition hover:text-gold-bright">Pricing</a>
          <a href="/new"
             className="rounded border border-gold px-4 py-2 text-gold-bright transition hover:bg-gold hover:text-ink">
            Open the studio
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-24 pt-16 text-center">
        <div className="text-[11px] uppercase tracking-[0.4em] text-gold">
          An AI design studio with standards
        </div>
        <h1 className="font-display mx-auto mt-6 max-w-3xl text-5xl leading-tight text-ivory-bright sm:text-6xl">
          We don&apos;t generate designs.
          <br />
          We translate <em className="text-gold-bright">presence</em>.
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-ivory-dim">
          Twenty years of quiet authority. A family&apos;s occasion. A product&apos;s heft.
          The things that make you unmistakable rarely survive the trip onto a card,
          an invitation, a cover. Our studio of AI specialists exists to carry them across.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <a href="/new"
             className="rounded bg-gold px-8 py-3.5 text-sm font-medium tracking-wide text-ink transition hover:bg-gold-bright">
            Start a project — watch it happen
          </a>
        </div>
        <div className="gold-rule mx-auto mt-16 w-56" />
      </section>

      {/* What we make */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-24">
        <div className="grid gap-px overflow-hidden rounded border border-ivory-dim/15 bg-ivory-dim/15 sm:grid-cols-3">
          {[
            ["Visiting cards", "the handshake that stays behind"],
            ["Wedding suites", "lineage, held in the hand"],
            ["Book covers", "the argument before page one"],
            ["Letterheads", "authority at document scale"],
            ["Product films", "8 seconds of presence, from one photo"],
            ["Brand marks", "a silhouette that survives being small"],
          ].map(([name, line]) => (
            <div key={name} className="bg-ink-soft p-8">
              <div className="font-display text-2xl text-ivory-bright">{name}</div>
              <div className="mt-2 text-sm text-ivory-dim">{line}</div>
            </div>
          ))}
        </div>
      </section>

      {/* The craft */}
      <section id="craft" className="mx-auto w-full max-w-6xl px-6 pb-24">
        <h2 className="font-display text-center text-4xl text-ivory-bright">
          Why it doesn&apos;t look like AI made it
        </h2>
        <div className="mt-12 grid gap-10 sm:grid-cols-2">
          {CRAFT.map((c, i) => (
            <div key={c.title} className="border-l border-gold/40 pl-6">
              <div className="text-[10px] uppercase tracking-[0.3em] text-gold">
                {String(i + 1).padStart(2, "0")}
              </div>
              <h3 className="font-display mt-2 text-2xl text-ivory-bright">{c.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ivory-dim">{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* The theater pitch */}
      <section className="mx-auto w-full max-w-4xl px-6 pb-24 text-center">
        <div className="rounded border border-gold/30 bg-ink-soft px-8 py-14">
          <div className="text-[11px] uppercase tracking-[0.35em] text-gold">The agent theater</div>
          <h2 className="font-display mx-auto mt-4 max-w-2xl text-3xl leading-snug text-ivory-bright">
            You don&apos;t submit a form and wait.
            You watch a studio work.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-ivory-dim">
            The producer casts the crew in front of you. Specialists spawn, argue their
            direction, and hand work to the critic. Thumbnails develop like polaroids
            the second they render. When the lights come up, your gallery is hung —
            each design with the reason it&apos;s you.
          </p>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="mx-auto w-full max-w-6xl px-6 pb-24">
        <h2 className="font-display text-center text-4xl text-ivory-bright">Pricing</h2>
        <p className="mt-3 text-center text-sm text-ivory-dim">
          Per project. See everything before you pay anything.
        </p>
        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {PRICING.map((tier) => (
            <div key={tier.name}
                 className={`rounded border p-8 ${
                   tier.featured ? "border-gold bg-ink-soft" : "border-ivory-dim/20 bg-ink-soft/50"
                 }`}>
              <div className="font-display text-2xl text-ivory-bright">{tier.name}</div>
              <div className="mt-2 text-lg text-gold-bright">{tier.price}</div>
              <ul className="mt-6 space-y-2 text-sm text-ivory-dim">
                {tier.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-gold">·</span>{f}
                  </li>
                ))}
              </ul>
              <a href={tier.href}
                 className={`mt-8 block rounded px-5 py-2.5 text-center text-sm transition ${
                   tier.featured
                     ? "bg-gold text-ink hover:bg-gold-bright"
                     : "border border-ivory-dim/40 text-ivory hover:border-gold"
                 }`}>
                {tier.cta}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-ivory-dim/10">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-10 text-xs text-ivory-dim/70">
          <span className="font-display text-base text-ivory-dim">
            AURA <span className="text-gold">Studio</span>
          </span>
          <span>Designs that carry who you are.</span>
        </div>
      </footer>
    </main>
  );
}
