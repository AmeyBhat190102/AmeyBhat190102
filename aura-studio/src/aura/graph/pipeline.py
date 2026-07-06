"""The studio, as a LangGraph state machine.

    intake -> extract_aura -> direct --Send--> design_render (xN, parallel)
                                                    |
                                                 review  <---- revise (xM, parallel)
                                                    | (all shippable, or revision budget spent)
                                                 curate -> END

Dynamic behavior:
- The creative director chooses N (fan-out width) per brief.
- The critic decides, per candidate, whether it loops back for revision —
  bounded by settings.max_revisions so cost stays predictable.
- A revised candidate *replaces* its predecessor (state is keyed by
  direction), so curation only ever sees the latest attempt per direction.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from aura.agents.aura_extractor import extract_aura
from aura.agents.concept_designer import design_concept
from aura.agents.creative_director import plan_directions
from aura.agents.critic import critique
from aura.agents.curator import curate
from aura.agents.intake import run_intake
from aura.config import Providers, Settings
from aura.render.executor import render_candidate
from aura.schemas import (
    AuraProfile, Candidate, ConceptDirection, Critique, DeliverablePackage,
    DesignBrief, InputAsset,
)


def _merge_dicts(left: dict, right: dict) -> dict:
    return {**left, **right}


class StudioState(TypedDict, total=False):
    request_text: str
    assets: list[InputAsset]
    brief: DesignBrief
    aura: AuraProfile
    directions: list[ConceptDirection]
    candidates: Annotated[dict[str, Candidate], _merge_dicts]   # direction_id -> latest
    critiques: Annotated[dict[str, Critique], _merge_dicts]     # candidate_id -> critique
    package: DeliverablePackage


def build_graph(providers: Providers, settings: Settings, store):
    async def intake_node(state: StudioState) -> dict:
        if state.get("brief"):  # caller may supply a prebuilt brief
            return {}
        brief = await run_intake(providers.llm, request_text=state["request_text"],
                                 assets=state.get("assets", []))
        return {"brief": brief}

    async def aura_node(state: StudioState) -> dict:
        return {"aura": await extract_aura(providers.llm, state["brief"])}

    async def direct_node(state: StudioState) -> dict:
        directions = await plan_directions(providers.llm, state["brief"], state["aura"], settings)
        return {"directions": directions}

    def fan_out(state: StudioState) -> list[Send]:
        return [Send("design_render", {"direction": d, "brief": state["brief"],
                                       "aura": state["aura"]})
                for d in state["directions"]]

    async def design_render_node(payload: dict) -> dict:
        spec = await design_concept(providers.llm, brief=payload["brief"],
                                    aura=payload["aura"], direction=payload["direction"])
        candidate = await render_candidate(providers, store, brief=payload["brief"],
                                           direction=payload["direction"], spec=spec)
        return {"candidates": {payload["direction"].direction_id: candidate}}

    async def review_node(state: StudioState) -> dict:
        pending = [c for c in state["candidates"].values()
                   if c.candidate_id not in state.get("critiques", {})]
        results = await asyncio.gather(*[
            critique(providers.llm, brief=state["brief"], aura=state["aura"],
                     candidate=c, threshold=settings.ship_threshold)
            for c in pending
        ])
        return {"critiques": {r.candidate_id: r for r in results}}

    def route_after_review(state: StudioState):
        sends = []
        for candidate in state["candidates"].values():
            verdict = state["critiques"][candidate.candidate_id]
            if verdict.verdict == "revise" and candidate.revision < settings.max_revisions:
                sends.append(Send("revise", {
                    "brief": state["brief"], "aura": state["aura"],
                    "candidate": candidate, "notes": verdict.revision_notes,
                }))
        return sends or "curate"

    async def revise_node(payload: dict) -> dict:
        old: Candidate = payload["candidate"]
        spec = await design_concept(
            providers.llm, brief=payload["brief"], aura=payload["aura"],
            direction=old.direction, revision_notes=payload["notes"],
            previous_spec=old.spec)
        candidate = await render_candidate(
            providers, store, brief=payload["brief"], direction=old.direction,
            spec=spec, revision=old.revision + 1)
        return {"candidates": {old.direction.direction_id: candidate}}

    async def curate_node(state: StudioState) -> dict:
        package = await curate(
            providers.llm, brief=state["brief"], aura=state["aura"],
            candidates=list(state["candidates"].values()),
            critiques=state["critiques"], final_count=settings.final_count)
        return {"package": package}

    g = StateGraph(StudioState)
    g.add_node("intake", intake_node)
    g.add_node("extract_aura", aura_node)
    g.add_node("direct", direct_node)
    g.add_node("design_render", design_render_node)
    g.add_node("review", review_node)
    g.add_node("revise", revise_node)
    g.add_node("curate", curate_node)

    g.add_edge(START, "intake")
    g.add_edge("intake", "extract_aura")
    g.add_edge("extract_aura", "direct")
    g.add_conditional_edges("direct", fan_out, ["design_render"])
    g.add_edge("design_render", "review")
    g.add_conditional_edges("review", route_after_review, ["revise", "curate"])
    g.add_edge("revise", "review")
    g.add_edge("curate", END)
    return g.compile()


async def run_studio(providers: Providers, settings: Settings, store, *,
                     request_text: str, assets: list[InputAsset] | None = None,
                     brief: DesignBrief | None = None) -> DeliverablePackage:
    graph = build_graph(providers, settings, store)
    initial: StudioState = {"request_text": request_text, "assets": assets or [],
                            "candidates": {}, "critiques": {}}
    if brief:
        initial["brief"] = brief
    final = await graph.ainvoke(initial)
    return final["package"]
