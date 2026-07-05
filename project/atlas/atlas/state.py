"""State schemas for the Atlas graph and the research subgraph.

Concepts on display:
- `MessagesState` extension (inherits the `add_messages` reducer)
- Custom reducers via `Annotated[..., reducer]`
- A subgraph with a *different, private* schema than its parent
- Per-branch state for `Send` fan-out (map-reduce)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import MessagesState

AgentName = Literal["support", "analyst", "researcher"]


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Reducer: shallow-merge dict updates instead of overwriting."""
    return {**(left or {}), **(right or {})}


class AtlasState(MessagesState):
    """Parent graph state. `messages` (with add_messages) comes from MessagesState."""

    # Routing decision made by the supervisor each cycle.
    next_agent: AgentName | Literal["respond"] | None
    # Why the supervisor routed there (surfaced to the UI via `updates` streaming).
    routing_reason: str | None
    # Notes contributed by the research subgraph; appended, never overwritten.
    research_notes: Annotated[list[str], operator.add]
    # Structured facts gathered by workers (order info, stats, ...), merged.
    facts: Annotated[dict[str, Any], merge_dicts]
    # Which workers have run this turn (guards against routing loops).
    # Plain field (overwrite semantics): reset to [] at the start of each turn.
    visited: list[str]


# --------------------------------------------------------------------------- #
# Research subgraph: private schema, invisible to the parent graph.
# --------------------------------------------------------------------------- #

class ResearchState(TypedDict):
    """Private state of the research subgraph."""

    topic: str
    subtopics: list[str]
    # Filled in parallel by Send() branches — must have a reducer.
    notes: Annotated[list[str], operator.add]
    summary: str


class SubtopicState(TypedDict):
    """Per-branch input carried by each Send() into `research_subtopic`."""

    topic: str
    subtopic: str


class ResearchInput(TypedDict):
    topic: str


class ResearchOutput(TypedDict):
    summary: str
    notes: list[str]
