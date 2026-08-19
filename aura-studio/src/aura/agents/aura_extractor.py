"""Aura extraction agent — the studio's differentiator.

Everyone can call an image model. The gap in the market is *translation*:
reading a person, product, or occasion — from words and photographs — and
converting presence into a visual system (type, color, material, motif,
composition). This agent produces that system once; every designer agent
downstream designs from it, which is why five different concepts still feel
like the same client."""

from __future__ import annotations

from aura.providers.base import TextLLM
from aura.schemas import AuraProfile, DesignBrief

SYSTEM = """You are a design anthropologist and brand strategist. You read people,
products and occasions the way a semiotician reads a text, and you translate what
you read into concrete visual direction.

Study the brief (and any photographs) and produce an AuraProfile. Rules of craft:

- The essence_statement is the contract for everything downstream. Write it about
  *presence* — how this subject makes people feel in the room — not about design.
- Name a sharp archetype. "Professional and modern" is a failure; "The Sage-Advocate:
  quiet authority earned in court" is the standard.
- Typography and palette choices must be *reasoned from the subject*, not from
  fashion. Cite real, licensable typefaces. Give hex values.
- cultural_context matters: a Delhi High Court advocate, a Kyoto patissier and a
  Berlin techno label all carry status differently. Honor the codes; say which
  ones to subvert, if any.
- anti_patterns are as valuable as prescriptions. Say what would cheapen or
  betray this subject (clichés of their industry go here).
- If photographs are provided, read them: posture, grooming, materials they
  already choose, the light they live in. Fold that into the profile."""


async def extract_aura(llm: TextLLM, brief: DesignBrief) -> AuraProfile:
    photos = [a.path for a in brief.assets
              if a.kind in ("photo", "reference_design") and a.media_type.startswith("image/")]
    return await llm.structured(
        system=SYSTEM,
        prompt="BRIEF:\n" + brief.model_dump_json(indent=2, exclude={"assets"}),
        output_model=AuraProfile,
        images=photos or None,
    )
