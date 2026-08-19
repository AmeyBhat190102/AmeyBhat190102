# AURA Studio — Enhancement Roadmap

How v0.2 becomes a product people pay for, recommend, and can't replace — and the exact tasks to get there.

This document is the working backlog. Phases are ordered by dependency and by what de-risks the business soonest: **quality first** (nobody pays for almost-good design), **flywheel second** (the data moat), **growth surface third**, **physical goods fourth**, **scale last** (scaling a thing nobody wants is the classic failure). Check items off in place; every task points at the real file or module it touches.

---

## 0. Where the product stands (v0.2, honest)

**Works, verified end to end:**
- Dynamic multi-agent engine: producer casts a per-brief crew (`aura-studio/src/aura/agents/producer.py`) over the role registry (`roles/library.py`); generic executor spawns agents in dependency order with failure isolation and budget metering (`graph/dynamic.py`, `graph/task_executor.py`, `providers/metering.py`)
- Durable runs: Postgres/sqlite checkpointing, arq worker resume-on-retry, clarify + studio-review interrupts (`worker.py`) — verified against real Postgres 16 + Redis
- Typed event bus → SSE agent theater (`events.py`, `bus.py`, `api/main.py`)
- Print-exact rendering: HTML/CSS → Chromium → PNG previews + mm-accurate PDFs (`render/`)
- Web app: wizard → theater → gallery → checkout (`web/src/app/`), dual-payment scaffolding (`web/src/lib/payments/`)
- 13 green tests (`aura-studio/tests/`), `docker compose up` runs the full stack

**Scaffolded but not closed:**
- Taste corpus is *written* (`db/models.py: TasteCorpusRow`, worker records every trace + pick) but never *read back* into prompts
- Studio-review gate works via API (`POST /projects/{id}/review`) but there is no editor UI
- `RECRAFT_API_KEY` exists in config; no `RecraftImageGen` provider implemented yet
- `web/src/lib/types.ts` is a hand-maintained mirror of engine schemas; `packages/contracts` codegen deferred
- No accounts (Auth.js planned, not wired), no observability, no rate limiting, no moderation
- Preview-tier previews are not watermarked (payment gating is on print/source files only)

**Mocked until keys are set:** all reasoning/image/video runs on mocks by default (`AURA_PROVIDERS=mock`). The rendering path is real either way.

---

## E1 — First real output: go live on quality

**Goal:** the same pipeline, running on real models, producing work a paying stranger accepts — with proof, not vibes.
**Why first:** every later phase (flywheel, growth, print) amplifies whatever quality exists. Amplifying mediocre output kills the brand fastest.

### Tasks

- [ ] **Turn the keys.** Set `ANTHROPIC_API_KEY`, `IDEOGRAM_API_KEY`, `REPLICATE_API_TOKEN` (see `aura-studio/.env.example`), flip `AURA_PROVIDERS=auto`, run 5 briefs across artifact types. Read every critic verdict.
- [ ] **Golden brief suite.** Create `aura-studio/evals/briefs/` with ~20 curated briefs (advocate card, doctor card, Hindi wedding suite, thriller book cover, kettle product film, café brand kit…), each with expected artifact type and rubric notes.
- [ ] **Eval harness.** `aura-studio/evals/run_evals.py`: run the suite nightly (mock in CI, real on schedule), persist critic scores per criterion per brief to a `eval_runs` table (add to `db/models.py`), fail loudly on score regression. Reuse `worker.run_project` — don't build a parallel path.
- [ ] **Prompt tuning loop.** Iterate the system prompts in `agents/aura_extractor.py`, `agents/producer.py`, `roles/library.py` against real eval scores. Track prompt versions in git; one change per commit so score deltas attribute cleanly.
- [ ] **RecraftImageGen provider** (`providers/image_gen.py`): native SVG for motifs/logos — print-scalable, composable with the layout engine. Wire into `config.py` selection; prefer it for `motif_illustrator` / `logo_designer` outputs.
- [ ] **Direct Veo 3.1 / Kling 3.0 model slugs** in `providers/video_gen.py` (currently one default slug); route by tier — Kling for standard, Veo for studio.
- [ ] **Watermark preview-tier renders.** Add a watermark overlay pass in `render/executor.py` when `tier == "preview"` (CSS layer in the layout engine — deterministic, free); remove on unlock re-render.
- [ ] **Upload + prompt moderation.** Screen uploaded images and briefs before the run starts (Anthropic moderation via the existing `TextLLM` protocol, in `api/main.py: create_project`).
- [ ] **Model routing config.** Per-role model overrides in `Settings` (`config.py`) so `aura_extractor`/`critic` (judge model) vs. crew roles (fast model) is tunable without code.

**Done when:** 20 golden briefs average ≥ 7.5/10 from the critic on real providers, zero misprinted hard facts across the suite, and nightly evals run unattended with score history.

---

## E2 — The quality flywheel + Studio ops

**Goal:** every delivered project makes the next one better. This is the moat — model vendors can copy the pipeline; they can't copy the corpus.
**Why second:** retrieval needs real projects to retrieve from, so it lands right after E1 starts producing them.

### Tasks

- [ ] **Taste retrieval.** `aura-studio/src/aura/taste.py`: given a new `AuraProfile`, fetch the top-k prior winners (same artifact type, similar archetype — start with keyword match on `TasteCorpusRow.archetype`, upgrade to embeddings later). Inject as few-shot exemplars into the producer and designer prompts (`agents/producer.py`, `graph/task_executor.py`).
- [ ] **Record *why* clients picked.** Extend `POST /projects/{id}/pick` (`api/main.py`) with an optional free-text reason; store on `TasteCorpusRow`; feed into retrieval snippets.
- [ ] **Editor review console.** `web/src/app/editor/page.tsx` (+ `[id]` detail): list projects in `waiting_review`, show candidates with previews and critic scores, approve/revise/reject with notes — driving the *existing* `POST /projects/{id}/review` API. Gate behind an editor token (mint with `web/src/lib/engine.ts: serviceToken` pattern; add proper editor auth in E3).
- [ ] **Critic calibration.** Log editor overrides (editor rejected what the critic shipped, or vice versa) into `TasteCorpusRow.editor_notes`; monthly job compares critic scores vs. editor/client outcomes and reports rubric drift.
- [ ] **Model A/B by pick-rate.** Tag each candidate with its render provider/model in `Candidate` (`schemas.py`); dashboard query: pick-rate per model per artifact class. Route future traffic to winners (`config.py`).
- [ ] **Revision chat backend.** `POST /projects/{id}/revise`: client message → validated into `Critique(verdict="revise", revision_notes=[...])` for the chosen candidate → re-enqueue with `Command(resume=...)` or targeted `revise` entry. The graph loop already exists (`graph/dynamic.py: revise_node`); this exposes it to paying clients post-delivery.

**Done when:** designer prompts contain retrieved winners on every real run; an editor can clear the review queue without touching curl; pick-rate per model is a queryable number.

---

## E3 — Product & growth surface

**Goal:** the loops that bring the next customer in — accounts, sharing, SEO — built on the studio's transparency as the differentiator.

### Tasks

- [ ] **Auth.js v5 accounts.** `web/src/auth.ts` + `app/api/auth/[...nextauth]/route.ts` (Google + email), JWT sessions; mint engine tokens with `web/src/lib/engine.ts: userToken`. Engine already enforces accounts for paid tiers (`api/main.py`).
- [ ] **Project dashboard.** `web/src/app/dashboard/page.tsx`: user's projects, statuses, re-download, revision entry point.
- [ ] **Revision chat UI.** Thread view on the gallery page posting to the E2 endpoint; show the resulting new render inline when the run completes (the SSE theater already covers the live part).
- [ ] **Aura mirror.** Public opt-in share card per project — archetype, palette swatches, typefaces, essence line — at `web/src/app/aura/[id]/page.tsx` with OG image (render via the engine's own layout engine: eat the dog food). Links to `/new`.
- [ ] **Critic-scored public gallery.** `web/src/app/gallery/page.tsx`: anonymized best work with real critic scores and one-line notes. Server-rendered, indexed — this is the SEO engine. Needs a `public_ok` flag on projects + an opt-in checkbox at brief time.
- [ ] **Live homepage window.** Anonymized SSE relay of in-flight projects (strip names/hard facts server-side — new engine endpoint `GET /public/feed`) replacing the static theater pitch on `web/src/app/page.tsx`.
- [ ] **Delivered counter.** Footer counter from a cheap `COUNT(*)` endpoint; cache 60s.
- [ ] **Contracts codegen.** `packages/contracts/`: export FastAPI `openapi.json` → generate the TS client (orval) → delete the hand-mirror `web/src/lib/types.ts`. Add `make contracts` + CI check that it's fresh.

**Done when:** a stranger can sign up, run a project, share their aura card, and the public gallery ranks for "AI business card design" queries with real scored work.

---

## E4 — Physical goods (v1.5)

**Goal:** "designs + the object at your door." The service moat software-only competitors won't copy quickly.

### Tasks

- [ ] **`FulfillmentProvider` protocol** (`aura-studio/src/aura/fulfillment/base.py`): `quote(artifact, options)`, `submit_order(pdf, options, address)`, `webhook(status)` — mirroring the payments pattern in `web/src/lib/payments/provider.ts`.
- [ ] **Prodigi provider** (global print API) + **PrintStop/Inkmonk** (India). Route by shipping country.
- [ ] **Paper/finish options** as data on `ArtifactType` (`schemas.py`) — 400gsm, cotton, letterpress, foil — priced into checkout (`web/src/app/checkout/[id]/page.tsx`).
- [ ] **Orders table + webhooks** (`db/models.py`, order status events into the existing `project_events` stream → dashboard).
- [ ] **Print QA loop.** Order one physical proof per new artifact type/finish before offering it; log defects against the render settings (bleed, color profile) in `render/html_renderer.py`.

**Done when:** a customer in Mumbai and one in Berlin each receive a printed card whose colors and margins match the on-screen proof.

---

## E5 — Scale & hardening

**Goal:** boring reliability. Do this when there's traffic worth protecting.

### Tasks

- [ ] **Langfuse tracing** wrapped around `providers/anthropic_llm.py` + image/video providers; cost-per-project dashboard replacing the static `PRICES` table in `providers/metering.py` as the source of truth (keep `PRICES` as the governor).
- [ ] **Sentry** in both `api/main.py` and `web/` (Next instrumentation).
- [ ] **Rate limiting** on `POST /projects` (per-IP for anonymous preview tier — this is the free-compute abuse surface).
- [ ] **S3/R2 artifact store**: second implementation of the two-method `ArtifactStore` (`storage.py`); signed URLs replace `FileResponse` streaming in `api/main.py`.
- [ ] **CI**: GitHub Actions — `pytest` (mock mode), `eslint` + `next build`, contracts freshness; on PR to the default branch.
- [ ] **Worker scaling**: `docker compose up --scale worker=N` already works (unique job ids prevent double-runs); document + add queue-depth metric.
- [ ] **SSE load test** (many concurrent theaters) — verify the Redis pub/sub fanout and Postgres replay under load; add connection caps.
- [ ] **Backups & retention**: Postgres backups (checkpoints included), artifact retention policy for unpaid preview projects (30-day purge job).

**Done when:** a provider outage, a traffic spike, or a worker crash is an alert and a graph, not a customer-facing mystery.

---

## Sequencing at a glance

| Order | Phase | Depends on | Size | The risk it retires |
|---|---|---|---|---|
| 1 | E1 quality | keys, budget for real runs | M | "is the output actually good enough to sell?" |
| 2 | E2 flywheel | E1 producing real projects | M | "why won't a model release erase us?" |
| 3 | E3 growth | E2 partially (gallery needs scored work) | L | "how does the next customer find us?" |
| 4 | E4 print | E1 quality bar; E3 accounts helpful | M | "what stops a pure-software copycat?" |
| 5 | E5 scale | real traffic | M | "can we survive success?" |

Rough sizing: S ≈ a day, M ≈ a week, L ≈ 2–3 weeks of focused work. E1→E2 is the critical path; E3 items can interleave once the gallery has ≥ 20 scored real projects to show.

## The one metric

Everything above serves a single number, carried over from [`aura-studio/docs/STRATEGY.md`](aura-studio/docs/STRATEGY.md): **aura fidelity as judged by the client's circle** — "people who know you say *that's you*." Operationalized as pick-rate + post-delivery survey + repeat/referral rate. Speed and cost per project are table stakes; if an enhancement doesn't raise that number or protect the corpus that feeds it, it waits.
