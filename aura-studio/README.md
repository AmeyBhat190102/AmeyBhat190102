# AURA Studio

**A multi-agent design intelligence studio.** Multimodal brief in → 4–5 gallery-grade designs out, each with the rationale for why it fits.

The thesis: the gap in the design market isn't *generation* — it's **translation**. A senior advocate carries twenty years of quiet authority; almost no visiting card he can buy carries it for him. AURA reads a person, product, or occasion (from words, photos, and documents) and translates that presence — the *aura* — into artifacts: business cards, wedding invitations, book covers, posters, product-shoot films, and anything else the artifact registry learns.

## How it works

```
 multimodal brief ──▶ INTAKE ──▶ AURA EXTRACTION ──▶ CREATIVE DIRECTOR
 (text + photos)      structured   visual DNA:          stakes out 4–6 distinct
                      DesignBrief  type, palette,       concept directions
                                   material, motif      (dynamic fan-out)
                                        │                     │
                                        ▼                     ▼
                     CURATOR ◀── CRITIC LOOP ◀── CONCEPT DESIGNERS (parallel)
                     top 4–5 by     vision-model     each direction → DesignSpec
                     quality ×      review; weak     routed by artifact class
                     diversity,     work revised
                     + rationale    (bounded loop)
                     cards               ▲
                                         └── RENDER: layout engine / image gen / video gen
```

The pipeline is a LangGraph state machine (`src/aura/graph/pipeline.py`) with dynamic fan-out (`Send`): the creative director decides how many concepts a brief deserves; the critic decides per-candidate whether work loops back for revision.

## The three quality decisions

1. **Typography is code, not diffusion.** Print artifacts (cards, invites) are designed as HTML/CSS and rendered by Chromium at physical size — pixel-perfect names and phone numbers, print-ready PDFs with real millimeters. Image models only paint backgrounds and motifs *under* the type. This is the difference between a demo and something a print house accepts.
2. **Aura extraction is a dedicated stage.** One agent converts the subject into a visual system (archetype, typefaces, palette hex, materials, motifs, anti-patterns). Every designer works *from that profile*, so five different concepts still unmistakably belong to the same client.
3. **Nothing ships unjudged.** A vision critic scores every rendered candidate against a fixed rubric (aura fidelity, craft, legibility, production safety, distinctiveness), sends weak work back with concrete notes, and kills concept-level failures. Curation maximizes quality × diversity, not raw score.

## Quickstart

```bash
cd aura-studio
uv venv && uv pip install -e ".[dev]"

# Full pipeline, no API keys needed (mock reasoning, REAL rendering):
AURA_PROVIDERS=mock .venv/bin/aura \
  "Design a visiting card for Adv. R. K. Sharma, senior advocate, 20 years in constitutional law. Understated, premium."

# Production: set keys and go
export ANTHROPIC_API_KEY=...       # agent reasoning + vision critique
export IDEOGRAM_API_KEY=...        # or OPENAI_API_KEY — generated artwork
export REPLICATE_API_TOKEN=...     # Veo/Kling image-to-video product films
.venv/bin/aura "8-second product film for our ceramic pour-over kettle" \
  --asset kettle.jpg="hero product photo, studio light"

# API server
.venv/bin/uvicorn aura.api.main:app
# POST /projects (multipart: brief + files) → job → GET /projects/{id}
```

```bash
.venv/bin/python -m pytest   # end-to-end tests run offline; Chromium renders for real
```

## Layout

```
src/aura/
  schemas.py            # typed contracts between every stage (+ artifact registry)
  config.py             # env-driven settings & provider wiring (auto/mock)
  agents/               # intake, aura_extractor, creative_director,
                        # concept_designer (incl. cinematographer), critic, curator
  graph/pipeline.py     # LangGraph orchestration: fan-out, critique loop, curation
  providers/            # TextLLM / ImageGen / VideoGen protocols + Anthropic,
                        # OpenAI/Ideogram, Replicate(Veo/Kling), mocks
  render/               # Chromium layout engine (PNG + print PDF), spec executor
  api/main.py           # FastAPI: submit brief + files, poll, download deliverables
  cli.py                # terminal studio
docs/
  ARCHITECTURE.md       # full system design & extension guide
  STRATEGY.md           # breadth-first → niche-domination plan
```

## Extending

- **New artifact type** (menu, album sleeve, packaging…): add an entry to `ARTIFACT_TYPES` in `schemas.py` with its render route and physical specs. No new code.
- **New render route** (3D, motion graphics…): add an `ArtifactClass`, a spec model, a designer system prompt, and an executor branch.
- **New model vendor**: implement one protocol from `providers/base.py`, wire it in `config.py`.
