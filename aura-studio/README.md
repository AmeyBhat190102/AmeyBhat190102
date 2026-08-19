# AURA Studio — the engine

**A multi-agent design intelligence studio.** Multimodal brief in → a runtime-cast crew of AI specialists → 4–5 gallery-grade designs out, each with the rationale for why it fits. This directory is the Python engine + API; the customer-facing web app lives in [`../web`](../web), and one `docker compose up` at the repo root runs the whole product.

The thesis: the gap in the design market isn't *generation* — it's **translation**. A senior advocate carries twenty years of quiet authority; almost no visiting card he can buy carries it for him. AURA reads a person, product, or occasion (from words, photos, documents) and translates that presence — the *aura* — into artifacts: business cards, wedding invitations, book covers, posters, product films.

## How it works (v0.2 — the dynamic studio)

```
 brief ─▶ INTAKE ─▶ CLARIFY(⏸) ─▶ AURA EXTRACTION ─▶ PRODUCER casts a crew
                                                          │  (WorkPlan: task DAG
                                                          │   over registered roles)
                                                          ▼
              SCHEDULE ⇄ Send("execute_task" × ready)  — specialists spawn in
                 │        copywriter · type specialist · motif illustrator ·
                 │        layout designers · cinematographer · sound director…
                 ▼
              CRITIC LOOP ⇄ REVISE ─▶ STUDIO GATE(⏸ human editor, Studio tier)
                 │
              CURATE ─▶ deliverables + rationale cards
```

- **Dynamic agent spawning.** No fixed pipeline: a producer agent reads the brief + aura and emits a validated `WorkPlan` — which specialists to cast, with what instructions, in what dependency order, within what budget. A wedding invite gets a copywriter, a calligraphy specialist and a motif illustrator; a product film gets a cinematographer and a sound director. Roles are registry entries (`src/aura/roles/library.py`): adding a specialist is data, not graph surgery. If the producer emits an invalid plan three times, a deterministic template plan takes over — planning can never kill a paid project.
- **Durable by construction.** LangGraph checkpoints every superstep into Postgres (`thread_id = project_id`); arq retries resume mid-graph — a crash after 20 minutes of video generation never redoes the LLM work. Two `interrupt()` gates park the run across restarts: blocking client questions (`clarify`) and the Studio-tier human-editor review.
- **Everything narrated.** Every node emits typed `ProjectEvent`s → Postgres (replayable by `Last-Event-ID`) + Redis pub/sub → SSE. The web app's *agent theater* renders this stream live: specialists spawning, thumbnails developing, critic verdicts landing.
- **Typography is code, not diffusion.** Print artifacts are HTML/CSS rendered by Chromium at physical size — verbatim names and numbers, mm-accurate print PDFs. Image models paint motifs and backgrounds *under* the type (generated motifs flow into layouts as `__MOTIF_n__` tokens, inlined at render time).
- **Nothing ships unjudged.** A vision critic scores rendered pixels on a fixed rubric; weak work loops back with notes (bounded); curation guarantees the gallery spans safe → bold. Every project's full trace + the client's pick lands in the taste-corpus table — the compounding moat.
- **Cost-governed.** A `ToolBelt` meters every provider call against the project's budget; exhausted budgets degrade gracefully (`budget_denied` tasks, salvage delivery) instead of hanging. Budget caps per tier are pricing knobs in `Settings`.

## Quickstart

```bash
# The whole product (engine + worker + web + Postgres + Redis):
docker compose up            # from the repo root, mock providers by default

# Engine only, keyless dev (sqlite + inline jobs + mock reasoning, REAL rendering):
cd aura-studio && uv venv && uv pip install -e ".[dev]"
.venv/bin/uvicorn aura.api.main:app --port 8800

# Production providers — set keys and flip AURA_PROVIDERS=auto:
#   ANTHROPIC_API_KEY   agent reasoning + vision critique
#   IDEOGRAM_API_KEY / OPENAI_API_KEY   generated artwork
#   REPLICATE_API_TOKEN Veo/Kling image-to-video
# Infra: DATABASE_URL (postgres), REDIS_URL (arq + live events)

.venv/bin/python -m pytest   # 13 tests: dynamic runs, interrupt/resume, API, payment gating
```

## API

| Route | Purpose |
|---|---|
| `POST /projects` | submit brief + files → queued project (tier: preview/standard/studio) |
| `GET /projects/{id}` | status, plan, task board, package |
| `GET /projects/{id}/events` | SSE — replays history, then live tail |
| `POST /projects/{id}/answers` | resume a clarify interrupt |
| `POST /projects/{id}/review` | resume a studio-review interrupt (editor token) |
| `POST /projects/{id}/pick` | client's chosen design → taste corpus |
| `POST /projects/{id}/unlock` | payment webhook target (service token) |
| `GET /projects/{id}/files/{artifact}` | previews free; print/source files payment-gated |

## Layout

```
src/aura/
  schemas.py             typed contracts + artifact registry + interrupt payloads
  planning/schemas.py    AgentRole · TaskNode · WorkPlan (validated DAG) · RunBudget
  roles/                 the launch crew: registry + role library + output models
  agents/                intake, aura_extractor, producer, concept_designer,
                         critic, curator (+ legacy creative_director)
  graph/dynamic.py       the dynamic studio graph (Send fan-out, interrupts)
  graph/task_executor.py one spawned specialist: inputs → output → render → events
  graph/pipeline.py      v0.1 fixed pipeline (kept for reference/CLI)
  providers/             TextLLM/ImageGen/VideoGen protocols · Anthropic ·
                         Ideogram/OpenAI · Replicate video · metering · mocks
  render/                Chromium layout engine (PNG + print PDF) + spec executor
  db/                    SQLAlchemy models · repo · engine (postgres/sqlite)
  events.py, bus.py      typed event stream · Redis/local pub-sub
  worker.py              arq job runner + checkpointer + event pump (+ inline dev mode)
  api/                   FastAPI surface + JWT verification
migrations/              Alembic (production schema changes)
docs/                    ARCHITECTURE.md · STRATEGY.md
```

## Extending

- **New artifact type** (menu, album sleeve, packaging): add to `ARTIFACT_TYPES` in `schemas.py`.
- **New specialist**: register an `AgentRole` + output schema in `roles/library.py` — the producer can cast it immediately.
- **New model vendor**: implement one protocol in `providers/base.py`, wire in `config.py`.
- **New render route** (3D, motion graphics): new `ArtifactClass` + spec model + executor branch.
