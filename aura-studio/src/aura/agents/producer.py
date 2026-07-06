"""Producer agent: reads the brief + aura and casts a crew.

This is where "agents spawned in real time based on the requirement"
happens: the producer emits a WorkPlan — a task DAG over registered roles —
and the generic executor spawns one agent per task. A wedding invite gets a
copywriter, a calligraphy specialist and a motif illustrator; a product film
gets a cinematographer and a sound director; the producer decides.

Failure posture: validation errors are re-prompted with the exact error
twice; if the model still can't produce a legal plan, a hardcoded
per-artifact-class template plan takes over — a run never dies at planning.
"""

from __future__ import annotations

from pydantic import ValidationError

from aura.config import Settings
from aura.planning.schemas import TaskNode, WorkPlan
from aura.providers.base import TextLLM
from aura.roles.registry import ROLE_REGISTRY, ensure_loaded, role_catalog
from aura.schemas import (
    ARTIFACT_TYPES, ArtifactClass, AuraProfile, ConceptDirection, DesignBrief,
)

SYSTEM = """You are the producer of an elite AI design studio. Given a client brief and
their aura profile, cast a crew: emit a WorkPlan — a dependency-ordered set of tasks,
each performed by one specialist role from the casting sheet below. You may ONLY cast
roles from this sheet.

CASTING SHEET:
{catalog}

Rules of production:
- You are also the creative director: design tasks (layout_designer, cover_artist,
  cinematographer) each carry a `direction` — a distinct creative territory with a
  thesis. Stake out {min_designs}-{max_designs} design tasks whose directions are
  genuinely different (blind-test different), spanning risk safe -> bold, each
  derived from the aura profile.
- Cast support craft where it raises quality: copywriter when words will be printed
  (invitations, taglines); calligraphy_specialist when type carries the artifact;
  motif_illustrator when symbols would mean something; sound_brief_writer for films.
  Support tasks come FIRST; design tasks depend on them via depends_on and receive
  their outputs via input_bindings (param name -> upstream task_id).
- input_bindings values must be existing task_ids (or "brief"/"aura", which are
  always provided). A design task that should use the copy deck binds e.g.
  "copy": "<copywriter task_id>".
- Mark nice-to-have tasks criticality="optional"; the run survives their failure.
- Allocate budget_usd per task within total_budget_usd = {budget}: cheap roles
  ~0.1, standard ~0.5, expensive (video) ~2.0.
- At most {max_tasks} tasks. Do NOT cast the critic — review is a fixed studio stage.

EXAMPLE 1 — wedding invitation (abridged):
  tasks:
    - task_id: copy1, role: copywriter, instructions: "Formal Hindi+English wording,
      elders first, auspicious phrasing", no deps
    - task_id: type1, role: calligraphy_specialist, instructions: "Devanagari-friendly
      pairing, ornamental but restrained", no deps
    - task_id: motif1, role: motif_illustrator, instructions: "3 motifs: peacock rule,
      marigold corner, family monogram", no deps
    - task_id: design1..design4, role: layout_designer, depends_on: [copy1, type1,
      motif1], input_bindings: {{"copy": "copy1", "type_plan": "type1", "motifs":
      "motif1"}}, each with a distinct direction (heritage letterpress / modern
      minimal / royal ornament / bold contemporary)

EXAMPLE 2 — product film (abridged):
  tasks:
    - task_id: shots1, role: cinematographer, instructions: "8s hero film from the
      product photo, heritage mood", direction attached
    - task_id: sound1, role: sound_brief_writer, depends_on: [shots1],
      input_bindings: {{"shot_list": "shots1"}}, criticality: optional
"""


async def produce_plan(llm: TextLLM, *, brief: DesignBrief, aura: AuraProfile,
                       settings: Settings, budget_usd: float) -> WorkPlan:
    ensure_loaded()
    artifact = ARTIFACT_TYPES[brief.artifact_type_key]
    system = SYSTEM.format(
        catalog=role_catalog(),
        min_designs=settings.min_directions, max_designs=settings.max_directions,
        budget=f"{budget_usd:.2f}", max_tasks=settings.max_plan_tasks,
    )
    prompt = ("ARTIFACT: " + artifact.model_dump_json()
              + "\n\nBRIEF:\n" + brief.model_dump_json(indent=2, exclude={"assets"})
              + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2))

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            plan = await llm.structured(system=system, prompt=prompt, output_model=WorkPlan)
            plan.validate_against_registry(set(ROLE_REGISTRY), settings.max_plan_tasks)
            return _rescale_to_cap(plan, budget_usd)
        except (ValidationError, ValueError, RuntimeError) as e:
            last_error = e
            prompt += (f"\n\nYour previous plan (attempt {attempt + 1}) was rejected:"
                       f"\n{e}\nEmit a corrected WorkPlan.")
    return template_plan(brief, aura, budget_usd, error=str(last_error))


def _rescale_to_cap(plan: WorkPlan, cap_usd: float) -> WorkPlan:
    """If the producer budgeted above the project cap, scale every task down
    proportionally — re-validated, so the plan always round-trips checkpoints."""
    if plan.total_budget_usd <= cap_usd:
        return plan
    scale = cap_usd / plan.total_budget_usd
    return WorkPlan.model_validate({
        **plan.model_dump(),
        "total_budget_usd": cap_usd,
        "tasks": [{**t.model_dump(), "budget_usd": round(t.budget_usd * scale, 4)}
                  for t in plan.tasks],
    })


def template_plan(brief: DesignBrief, aura: AuraProfile, budget_usd: float,
                  error: str = "") -> WorkPlan:
    """Deterministic fallback crew per artifact class — the safety net that
    guarantees planning can never kill a paid project."""
    artifact = ARTIFACT_TYPES[brief.artifact_type_key]
    risk_bands = ["safe", "balanced", "balanced", "bold"]

    def directions(n: int) -> list[ConceptDirection]:
        return [
            ConceptDirection(
                name=f"{adj.title()} {artifact.display_name}",
                thesis=f"A {adj} interpretation grounded in: {aura.essence_statement[:140]}",
                how_it_expresses_aura=f"Leans on {', '.join(aura.adjectives[:3])}.",
                differentiator=f"Territory #{i + 1}: the {adj} register.",
                risk_level=risk_bands[i % len(risk_bands)],  # type: ignore[arg-type]
            )
            for i, adj in enumerate(["classic", "modern", "expressive", "minimal"][:n])
        ]

    if artifact.artifact_class is ArtifactClass.MOTION:
        shots = TaskNode(role_key="cinematographer", title="Hero film shot list",
                         instructions="Plan the product film per the aura profile.",
                         budget_usd=min(2.0, budget_usd * 0.8),
                         direction=directions(1)[0])
        sound = TaskNode(role_key="sound_brief_writer", title="Sound direction",
                         instructions="Score the film.", depends_on=[shots.task_id],
                         input_bindings={"shot_list": shots.task_id},
                         criticality="optional", budget_usd=0.1)
        tasks = [shots, sound]
    else:
        role = ("layout_designer"
                if artifact.artifact_class is ArtifactClass.TYPOGRAPHIC_PRINT
                else "cover_artist")
        tasks = [
            TaskNode(role_key=role, title=f"Design: {d.name}",
                     instructions=f"Design the {artifact.display_name} in this direction: "
                                  f"{d.thesis}",
                     budget_usd=min(0.5, budget_usd / 5), direction=d)
            for d in directions(4)
        ]
    allocated = sum(t.budget_usd for t in tasks)
    if allocated > budget_usd:
        scale = budget_usd / allocated
        for t in tasks:
            t.budget_usd = round(t.budget_usd * scale, 4)
    return WorkPlan(
        rationale="Template plan (producer fallback"
                  + (f" after: {error[:200]}" if error else "") + ").",
        tasks=tasks, total_budget_usd=budget_usd,
    )
