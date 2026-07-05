"""The supervisor: a routing LLM that decides which specialist runs next.

It returns a `Command(goto=...)` — dynamic control flow decided at runtime —
instead of relying on static conditional edges. Structured output keeps the
routing decision machine-readable.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from atlas.state import AtlasState

SUPERVISOR_PROMPT = """You are the supervisor of a customer support platform called Atlas.
Route the conversation to exactly one destination per turn:

- support: order lookups, refunds, returns, account actions, saving customer preferences.
- analyst: spend summaries, order statistics, product/revenue rankings.
- researcher: product questions, troubleshooting, policy explanations that need \
knowledge-base research.
- respond: the workers have gathered everything needed (or the request is trivial \
small talk) — produce the final answer now.

Rules:
- Workers already visited this turn: {visited}. Do not send the conversation to a \
worker that has already run unless the user asked a genuinely new question.
- If the last worker message answers the user's request, choose "respond".
- Prefer at most two worker hops before responding.
"""


class RouteDecision(BaseModel):
    """Where to send the conversation next."""

    next_agent: Literal["support", "analyst", "researcher", "respond"] = Field(
        description="The single destination that should act next."
    )
    reason: str = Field(description="One short sentence explaining the choice.")


def make_supervisor_node(model: BaseChatModel):
    router = model.with_structured_output(RouteDecision)

    def supervisor(state: AtlasState) -> Command[Literal["support", "analyst", "researcher", "respond"]]:
        visited = state.get("visited") or []
        prompt = SUPERVISOR_PROMPT.format(visited=", ".join(visited) or "none")
        decision: RouteDecision = router.invoke(
            [SystemMessage(content=prompt), *state["messages"]]
        )
        # Safety valve: never loop a worker twice in one turn.
        goto = decision.next_agent
        if goto in visited:
            goto = "respond"
        return Command(
            goto=goto,
            update={"next_agent": goto, "routing_reason": decision.reason},
        )

    return supervisor
