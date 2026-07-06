"""Intake agent: raw multimodal request -> DesignBrief.

Understands *any* design ask, maps it to the closest artifact type in the
registry, extracts hard facts verbatim (names/phones/dates must never be
paraphrased — they get printed), and surfaces what it doesn't know as
clarifying questions with stated default assumptions, so the pipeline never
blocks on the client but the client can always steer."""

from __future__ import annotations

from aura.providers.base import TextLLM
from aura.schemas import ARTIFACT_TYPES, DesignBrief, InputAsset

SYSTEM = """You are the intake director of an elite design studio. Clients describe
what they need in their own words, with photos and documents attached. Your job:

1. Identify the artifact they need. Choose artifact_type_key from this registry:
{artifact_registry}
   Pick the closest match; note any mismatch in constraints.
2. Extract HARD FACTS verbatim — names, titles, phone numbers, emails, dates,
   venues. These will be printed on the artifact; copying them exactly is a
   correctness requirement, not a style choice.
3. Capture the subject richly: who this person/product/event is, what they do,
   what standing they hold. This feeds aura analysis downstream.
4. List stated preferences and constraints separately from your inferences.
5. For every material unknown, add an open_question with the default assumption
   you'll proceed on. Never invent facts to fill a gap.
"""


async def run_intake(llm: TextLLM, *, request_text: str,
                     assets: list[InputAsset]) -> DesignBrief:
    registry = "\n".join(
        f"   - {t.key}: {t.display_name} ({t.artifact_class.value})"
        for t in ARTIFACT_TYPES.values()
    )
    asset_lines = "\n".join(
        f"- [{a.kind}] {a.asset_id}: {a.description or a.path}" for a in assets
    ) or "(none)"
    brief = await llm.structured(
        system=SYSTEM.format(artifact_registry=registry),
        prompt=f"CLIENT REQUEST:\n{request_text}\n\nATTACHED ASSETS:\n{asset_lines}",
        output_model=DesignBrief,
        images=[a.path for a in assets if a.media_type.startswith("image/")] or None,
    )
    brief.assets = assets  # authoritative asset list comes from us, not the model
    return brief
