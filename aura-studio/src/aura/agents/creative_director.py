"""Creative director agent: decides *how many* concepts to explore and stakes
out genuinely different territories for them.

The fan-out is dynamic: an ambiguous or high-stakes brief earns more
directions (up to max), a tightly-specified one fewer (down to min). Sibling
directions are forced apart — the classic studio failure mode is five
variations of one idea, and the differentiator field exists to prevent it."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aura.config import Settings
from aura.providers.base import TextLLM
from aura.schemas import AuraProfile, ConceptDirection, DesignBrief

SYSTEM = """You are the creative director of a design studio known for range.
Given a brief and the client's aura profile, stake out {min_n}-{max_n} concept
directions for the same artifact.

Requirements:
- Each direction argues ONE idea (its thesis). Not a mood, an argument.
- Directions must occupy different creative territories: if two of your
  directions could be confused for each other in a blind test, replace one.
  State each direction's differentiator against its siblings explicitly.
- Spread risk: at least one "safe" banker the client will certainly accept,
  at least one "bold" direction that reframes the brief. The rest "balanced".
- Every direction must still be *this client*: derive each from the aura
  profile and say how in how_it_expresses_aura. Range without fidelity is noise.
- Choose the count deliberately: more directions for ambiguous or high-stakes
  briefs, fewer for tightly constrained ones."""


class DirectionsBatch(BaseModel):
    directions: list[ConceptDirection] = Field(min_length=2)


async def plan_directions(llm: TextLLM, brief: DesignBrief, aura: AuraProfile,
                          settings: Settings) -> list[ConceptDirection]:
    batch = await llm.structured(
        system=SYSTEM.format(min_n=settings.min_directions, max_n=settings.max_directions),
        prompt=("BRIEF:\n" + brief.model_dump_json(indent=2, exclude={"assets"})
                + "\n\nAURA PROFILE:\n" + aura.model_dump_json(indent=2)),
        output_model=DirectionsBatch,
    )
    return batch.directions[: settings.max_directions]
