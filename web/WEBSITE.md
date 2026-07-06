# WEBSITE.md — The Glass Studio

The design spec for aura.studio's web presence. The site is not a SaaS landing page; it is **a working design studio you can see into**. Every screen must pass the studio's own critic: the site *is* the portfolio.

## The idea in one line

> Most AI products hide the machine. We put ours on stage — because watching a crew of specialists argue about *your* aura is the product demo, the trust builder, and the entertainment, all at once.

## Design language (the site's own aura)

Productized from our house card: **dark gallery, ivory type, one gold accent.**

| Token | Value | Role |
|---|---|---|
| `--ink` | `#14100c` | the room — near-black warm brown, never pure black |
| `--ivory` / `--ivory-bright` | `#e8ddc8` / `#f2ead6` | body / display type |
| `--gold` / `--gold-bright` | `#b08d4f` / `#d4af6a` | the single accent; used like foil — sparingly |
| `--crimson` | `#8d3b2e` | errors and kill verdicts only |
| Display | Cormorant Garamond | headlines, artifact names — the studio's voice |
| Body | Inter | UI, rationale text — the studio's hands |

Rules: generous whitespace is the status signal; small caps + wide tracking for labels (`text-[11px] uppercase tracking-[0.35em]`); hairline gold gradient rules as dividers; **no** drop shadows on type, **no** gradients that read digital, **no** stock imagery — every image on the site is studio output.

## The five screens

### 1. Landing — the studio window (`/`)
- Hero: *"We don't generate designs. We translate presence."* — the positioning is the headline.
- **One-of-a-kind element (v1.1): the live window.** Replace the static theater pitch with a real, anonymized feed of projects being designed right now — supervisor notes scrolling, thumbnails developing. Live proof beats any testimonial. (Requires an opt-in "show my project in the window" flag + an anonymized public SSE relay.)
- Artifact grid: six things we make, each with a one-line *reason* ("the handshake that stays behind"), not features.
- The craft: four numbered arguments for why output doesn't look AI-made (aura reading, dynamic crew, engineered type, the critic). This is the technical moat, told as craft.
- Pricing: three tiers, dual currency, "see everything before you pay anything."

### 2. Brief wizard — the intake conversation (`/new`)
- One question per screen, four steps: *what* → *who* (presence, not design preferences) → *hard facts, letter-for-letter* → *feel/never-be* + photo upload.
- Copy teaches the client to brief well: "Don't describe the design. Describe the person."
- Ends with "Reading your aura…" — the transition INTO the theater, not a spinner.

### 3. Agent theater — the floor (`/studio/[id]`)
- Two panes: **The crew** (task cards: specialist name, assignment, live status — spawning specialists appear as they're cast) and **From the floor** (narrated event feed: intake, aura reading, producer's casting rationale, critic verdicts with scores, thumbnails developing like polaroids).
- Aura card appears the moment it's read: archetype + palette swatches. This is the first "they *get* me" moment — arrives ~30s in, long before any design.
- Clarify panel: when the studio has a blocking question, it asks inline — answer or "proceed with your assumptions."
- v1.1: click a crew card to see that specialist's actual output (the copy deck, the type plan) — transparency as luxury.

### 4. The reveal — a gallery opening (`/studio/[id]` when done)
- Designs presented **one at a time, full-bleed, alternating sides** — never a thumbnail grid. Each with: risk label ("The banker" / "The considered choice" / "The statement"), direction name, rationale headline + body. Clients buy the *reason*, the pixels come free.
- "This is the one" pick per design → feeds the taste corpus (the moat).
- Unlock panel: watermark-free previews are already visible; payment unlocks print PDFs + sources.

### 5. Checkout (`/checkout/[id]`)
- One card, one price, dual currency, one button. Stripe redirect worldwide, Razorpay widget in India (geo-detected). No plan-comparison tables at the moment of purchase.

## What makes it one of a kind (roadmap of signature features)

1. **The live window** (above) — the homepage is a real studio floor.
2. **The aura mirror** — every project mints a shareable public card: archetype, palette, typefaces, essence line. "This is what an AI design studio read in me." Organic share loop; links back to /new.
3. **Critic-scored public gallery** — anonymized best work with the critic's actual scores and notes ("8.7 — restraint reads as intended"). Publishing our standards *is* the brand. Also the SEO engine.
4. **The revision chat** — post-delivery, clients talk to "their designer" in plain words; the message re-enters the graph as critique. Feels like a studio relationship, not a regenerate button.
5. **A delivered-designs counter** in the footer, live from the DB. Quiet, factual, compounding.

## Implementation notes

- Next.js 15 App Router in `web/`; engine reached via same-origin rewrite proxy (`/api/engine/*`) so SSE and cookies need zero custom code.
- Theater consumes the engine's typed SSE stream (`GET /projects/{id}/events`), with 4s polling as fallback; `Last-Event-ID` replay makes refreshes lossless.
- Payments: `PaymentProvider` interface (`src/lib/payments/`) — Stripe + Razorpay implementations, webhooks converge on the engine's `/unlock`. Dev mode with no keys unlocks instantly so the loop stays demoable.
- Auth.js v5 for accounts (dashboard, project history) — preview tier stays anonymous by design; lowest possible friction to the first "wow."
