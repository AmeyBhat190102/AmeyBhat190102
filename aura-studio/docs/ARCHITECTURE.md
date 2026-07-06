# AURA Studio — System Architecture

## 1. The problem, precisely

Clients don't lack image generators; they lack a **translator**. The value locked in a person, product, or occasion — an advocate's courtroom gravitas, a kettle's heft, a wedding's lineage — rarely survives the trip into a designed object. Human studios that do this well are slow and expensive. Raw gen-AI is fast but produces generic, unjudged, unprintable output. AURA's job is the translation itself, industrialized without losing taste.

## 2. Design principles

1. **Typed seams everywhere.** Every agent boundary is a pydantic model, enforced by forced-tool structured output with validation retry. An LLM pipeline is only as reliable as its least-validated hop.
2. **The right renderer per artifact, never one hammer.** *How you make it* is the quality decision:

   | Artifact class | Examples | Render route | Why |
   |---|---|---|---|
   | `typographic_print` | business cards, wedding invites, letterheads | LLM writes HTML/CSS → Chromium renders PNG preview + **print PDF at physical mm** | Diffusion garbles small type; a card is all small type. Code layouts give exact facts, real typefaces, bleed-safe margins, and infinite editability |
   | `illustrated_flat` | book covers, posters | image gen carries the art; any type composited as an HTML overlay *in the browser* | Art direction is gen-AI's strength; lettering still isn't |
   | `motion` | product-shoot films | cinematographer agent writes a shot list → image-to-video per shot from the client's photo → ffmpeg stitch | i2v anchored on the real product preserves brand fidelity; shot-level prompts control the camera like a DP would |

3. **Judgment is a stage, not a hope.** A vision critic sees the actual rendered pixels and scores a fixed rubric. Sub-threshold work loops back with actionable notes (bounded by `max_revisions`); conceptual failures die. Cost stays predictable, quality stays floored.
4. **One aura, many concepts.** Divergence happens at the *direction* level (5–6 territories), fidelity at the *profile* level (all designers consume the same AuraProfile). This is how you get range without losing the client.
5. **Vendors are config.** Four protocols (`TextLLM`, `ImageGen`, `VideoGen`, `LayoutRenderer`); the best model of the month is a one-line change. Mocks implement the same protocols, so the entire pipeline is testable offline — and because the layout engine is deterministic, even mock mode produces real cards.

## 3. Pipeline walkthrough

```
intake ─▶ extract_aura ─▶ direct ──Send──▶ design_render ×N  (parallel)
                                                │
                                             review ◀──────── revise ×M (parallel)
                                                │ all ship / budget spent
                                             curate ─▶ deliverables
```

LangGraph `StateGraph`; fan-out via the `Send` API; state reducers merge parallel branches (`candidates` keyed by direction so a revision *replaces* its predecessor).

| Stage | Agent (file) | In → Out | Notes |
|---|---|---|---|
| Intake | `agents/intake.py` | raw text + assets → `DesignBrief` | Maps request onto artifact registry; hard facts extracted **verbatim** (they get printed); unknowns become clarifying questions with stated default assumptions — pipeline never blocks, client can always steer |
| Aura extraction | `agents/aura_extractor.py` | brief + photos → `AuraProfile` | The moat. Archetype, essence, real typefaces, palette hex, materials, motifs, composition philosophy, **anti-patterns**. Vision reads posture/material/light from photos |
| Creative direction | `agents/creative_director.py` | brief + aura → 4–6 `ConceptDirection` | **Dynamic fan-out width**: ambiguous/high-stakes briefs earn more directions. Forced differentiation between siblings; risk spread safe→bold |
| Concept design | `agents/concept_designer.py` | direction → `DesignSpec` | Routed by artifact class (layout / image-prompt / shot-list system prompts). Same agent handles revisions with critic notes |
| Render | `render/executor.py` | spec → files | The only module touching engines. Background art injected under type as data-URI; overlay compositing done in Chromium; video stitched with ffmpeg when present |
| Review | `agents/critic.py` | rendered candidate → `Critique` | Rubric: aura_fidelity, craft, legibility, production safety, distinctiveness. Misprinted hard fact ⇒ automatic revise. Verdicts: ship / revise / kill |
| Curation | `agents/curator.py` | survivors → `DeliverablePackage` | Coverage-first selection (every risk band represented, then fill by score) + a client-facing rationale card per design |

## 4. Interfaces

- **API** (`api/main.py`): `POST /projects` (multipart brief + files) → job id; `GET /projects/{id}` → status/package; `GET /projects/{id}/files?path=` → deliverable download (allowlisted to the project's own outputs). Background tasks now; same endpoints over a real queue later.
- **CLI** (`cli.py`): `aura "<brief>" --asset photo.jpg="description"` — full studio run in the terminal.

## 5. Scaling path (deliberately not built yet)

- **Queue + workers** (SQS/Celery) behind the same job API; graph nodes are already async and stateless.
- **Checkpointed graphs** (LangGraph checkpointers) for resumability and human-in-the-loop approval between direction and design stages.
- **S3 artifact store** — `ArtifactStore` is a two-method interface for exactly this reason.
- **Taste corpus**: store every critique + client choice; fine-tune the critic and few-shot the designers on what actually got picked. This compounds — see STRATEGY.md.
- **Font licensing service**, brand-kit ingestion (existing logos/guidelines as constraints), and a review UI.

## 6. Cost & latency envelope

Per project (defaults: ≤6 directions, ≤2 revisions each): bounded at ~10–20 LLM calls, ≤6 image generations, ≤1 video job. The revision budget is the cost governor; raise `Settings.max_revisions`/`max_directions` for premium tiers, lower for volume tiers — it's a pricing knob, not a code change.
