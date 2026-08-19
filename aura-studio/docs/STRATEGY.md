# Strategy — breadth first, then own one niche

You said it yourself: explore the breadth of the industry, then pick one niche and become irreplaceable in it. Here's how this codebase encodes that plan, and where I'd place the niche bet.

## Phase 1 — Breadth (now): the engine IS the exploration

The architecture is built so breadth is cheap:

- A new artifact type is **registry data** (`ARTIFACT_TYPES`), not new code, as long as it fits an existing render route (typographic print / illustrated flat / motion). Menus, letterheads, album sleeves, event posters, packaging dielines — each is a config entry and maybe one designer-prompt tweak.
- Every project, regardless of vertical, produces the same telemetry: brief → aura → directions → critiques → **what the client actually picked**. That log is the exploration instrument. Run broad, watch where (a) willingness-to-pay is highest, (b) our critique scores beat local alternatives worst, (c) repeat/referral rates spike.

Ship fast here, price low, and treat every vertical as an experiment with the same pipeline.

## Phase 2 — The niche bet: identity artifacts

My recommendation, encoded in the demo and fixtures: **identity artifacts — business cards, wedding invitations, and the ceremony/professional stationery around them**, starting with markets where these objects still carry heavy social signaling (India is ideal: advocate/doctor/CA cards, wedding suites are a status economy with real budgets).

Why this niche, specifically:

1. **The aura-translation gap is widest here.** A book cover has a publisher's art director; a lawyer's card has a print shop with CorelDRAW templates. Nobody serves "make this object carry who I am" for individuals. That's our exact thesis.
2. **Quality is verifiable and defensible.** Print artifacts have objective failure modes (garbled type, unsafe margins, unprintable color) that pure-gen competitors reliably fail. Our layout-engine route wins blind tests *today* — we don't need to out-model anyone.
3. **It compounds into a moat.** Every delivered project grows the taste corpus: which archetypes chose which directions, which critiques predicted client choice. A fine-tuned critic + retrieval over won designs is a data moat no model release erases. The engine is replaceable; the corpus and the rubrics are not.
4. **Natural expansion path.** The person who loved their card orders the letterhead, the email signature, the wedding suite for their daughter, the firm's brand kit. Identity is a wedge into full personal/small-firm branding.

Product-video stays in the engine (it shares the pipeline and stretches the multimodal muscle) but as a Phase-1 breadth probe, not the core bet — that market is crowded with well-funded pure-video players, and our differentiation there is thinner.

## Phase 3 — Being un-replaceable

- **Own the last mile.** Integrate print fulfillment (paper stock, letterpress/foil partners, delivery). "Designs + the physical object at your door" is a service business AI companies won't copy easily; it also closes the quality loop (we see what print actually looks like).
- **Publish taste.** The critic's rubric, applied publicly (e.g., "we scored 100 advocate cards"), is content marketing that doubles as brand: we're the studio with *standards*.
- **Human editor in the loop at the top tier.** Sell tiers: Volume (pure pipeline), Studio (pipeline + human curator pass). The human pass trains the pipeline; the pipeline makes the human 20× productive. Competitors have one or the other.

## The one metric

**Aura fidelity as judged by the client's circle**: "people who know you say 'that's *you*'". Operationalize as post-delivery survey + repeat rate. Everything else (speed, cost per project) is table stakes.
