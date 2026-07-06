"""Curator: assemble the final gallery.

Selection is quality x diversity, not a raw top-K: five 8/10s from five
different territories beat five 9/10s that look alike. Each selected design
ships with a rationale card — clients don't buy pixels, they buy the reason
the pixels are *them*."""

from __future__ import annotations

import asyncio

from aura.providers.base import TextLLM
from aura.schemas import (
    AuraProfile, Candidate, Critique, DeliverablePackage, DesignBrief, RationaleCard,
)

RATIONALE_SYSTEM = """You write the studio's presentation notes. For the given design,
write a rationale card addressed to the client: a headline (<= 8 words) and a body
(2-3 sentences) explaining why this design carries *their* aura — grounded in the
aura profile and the direction's thesis. Confident, specific, zero jargon."""


def select_diverse(candidates: list[Candidate], critiques: dict[str, Critique],
                   k: int) -> list[Candidate]:
    """Coverage first, score second: the gallery must span the safe -> bold
    range before any band gets a second seat, then remaining slots fill by
    raw score. Delivered ordered best-first."""
    ranked = sorted(
        (c for c in candidates if critiques[c.candidate_id].verdict != "kill"),
        key=lambda c: critiques[c.candidate_id].overall, reverse=True,
    )
    chosen: list[Candidate] = []
    band_best = [next((c for c in ranked if c.direction.risk_level == band), None)
                 for band in ("safe", "balanced", "bold")]
    for c in sorted(filter(None, band_best),
                    key=lambda c: critiques[c.candidate_id].overall, reverse=True):
        if len(chosen) < k:
            chosen.append(c)
    chosen += [c for c in ranked if c not in chosen][: k - len(chosen)]
    return sorted(chosen, key=lambda c: critiques[c.candidate_id].overall, reverse=True)


async def curate(llm: TextLLM, *, brief: DesignBrief, aura: AuraProfile,
                 candidates: list[Candidate], critiques: dict[str, Critique],
                 final_count: int) -> DeliverablePackage:
    selected = select_diverse(candidates, critiques, final_count)
    rationales = await asyncio.gather(*[
        llm.structured(
            system=RATIONALE_SYSTEM,
            prompt=(f"candidate_id: {c.candidate_id}\n\n"
                    "DIRECTION:\n" + c.direction.model_dump_json(indent=2)
                    + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2)),
            output_model=RationaleCard,
        )
        for c in selected
    ])
    for card, c in zip(rationales, selected):
        card.candidate_id = c.candidate_id
    return DeliverablePackage(
        project_id=brief.project_id, brief=brief, aura=aura,
        selected=selected, rationales=list(rationales),
        rejected_count=len(candidates) - len(selected),
    )
