"""Critic agent: a vision-model design review against a fixed rubric.

Generation without judgment is a slot machine. Every rendered candidate is
scored by a critic that *sees the actual pixels* alongside the brief and
aura profile. Below-threshold work goes back to its designer with specific
notes (bounded revision loop); hopeless work is killed before curation."""

from __future__ import annotations

from aura.providers.base import TextLLM
from aura.schemas import AuraProfile, Candidate, Critique, DesignBrief

SYSTEM = """You are the studio's most feared design critic. You are looking at a
rendered candidate design. Score it 0-10 on exactly these criteria:

- aura_fidelity: does this artifact carry the client's presence as captured in
  the aura profile? Would someone who knows the client say "that's them"?
- craft: typography discipline, spacing rhythm, color control, composition.
- legibility: every printed fact readable at real-world size and distance.
- print_safety / production_safety: safe margins, no clipped elements, colors
  reproducible in the target medium.
- distinctiveness: would this survive next to the client's competitors' work,
  or is it template-grade?

Verdicts: "ship" if overall >= {threshold} with no criterion below 5;
"revise" if fixable — then every revision_note must be a concrete, actionable
instruction (name the element, say what to change); "kill" only for concept-level
failure a revision can't fix. Check hard facts character-by-character against the
brief; any misprinted fact caps legibility at 3 and forces at least "revise"."""


async def critique(llm: TextLLM, *, brief: DesignBrief, aura: AuraProfile,
                   candidate: Candidate, threshold: float) -> Critique:
    previews = [p for p in candidate.preview_paths if p.endswith(".png")]
    result = await llm.structured(
        system=SYSTEM.format(threshold=threshold),
        prompt=(f"candidate_id: {candidate.candidate_id}\n"
                f"revision: {candidate.revision}\n\n"
                "DIRECTION:\n" + candidate.direction.model_dump_json(indent=2)
                + "\n\nBRIEF HARD FACTS:\n" + "\n".join(
                    f"  {k}: {v}" for k, v in brief.hard_facts.items())
                + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2)
                + "\n\nSPEC (for reference):\n" + candidate.spec.model_dump_json(indent=2)),
        output_model=Critique,
        images=previews or None,
    )
    result.candidate_id = candidate.candidate_id  # never trust echoed ids
    return result
