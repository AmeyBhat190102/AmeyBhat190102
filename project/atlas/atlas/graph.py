"""Assembly of the Atlas parent graph.

Topology:

                    ┌────────────────────────────────────────┐
                    ▼                                        │
START ─▶ load_memory ─▶ supervisor ──(Command goto)──▶ support ──┐
                              │                     ├▶ analyst ──┤──▶ supervisor
                              │                     └▶ researcher┘
                              └────────▶ respond ─▶ END
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore

from atlas.agents.researcher import make_researcher_node
from atlas.agents.supervisor import make_supervisor_node
from atlas.agents.workers import ANALYST_PROMPT, SUPPORT_PROMPT, build_worker
from atlas.config import AtlasContext, get_model
from atlas.memory import get_preferences
from atlas.state import AtlasState
from atlas.tools.analyst_tools import ANALYST_TOOLS
from atlas.tools.support_tools import SUPPORT_TOOLS

RESPOND_PROMPT = """You are Atlas, a customer experience assistant.
Write the final reply to the customer based on the whole conversation, including
what the specialist agents (support / analyst / researcher) reported.
Be warm, precise, and concise. Honor these known customer preferences: {preferences}."""


def build_graph(
    model: BaseChatModel | None = None,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    model = model or get_model()

    # ------------------------------------------------------------------ nodes
    def load_memory(state: AtlasState, runtime: Runtime[AtlasContext]):
        """Start-of-turn hygiene: reset the loop guard, pull long-term memory."""
        customer_id = runtime.context.customer_id if runtime.context else "guest"
        preferences: list[str] = []
        if runtime.store is not None:
            preferences = get_preferences(runtime.store, customer_id)
        return {
            "visited": [],
            "facts": {"customer_id": customer_id, "preferences": preferences},
        }

    def respond(state: AtlasState):
        facts = state.get("facts") or {}
        system = RESPOND_PROMPT.format(preferences=facts.get("preferences") or "none")
        answer = model.invoke([SystemMessage(content=system), *state["messages"]])
        answer.name = "atlas"
        return {"messages": [answer]}

    supervisor = make_supervisor_node(model)
    support = build_worker("support", model, SUPPORT_TOOLS, SUPPORT_PROMPT)
    analyst = build_worker("analyst", model, ANALYST_TOOLS, ANALYST_PROMPT)
    researcher, research_graph = make_researcher_node(model)

    # ------------------------------------------------------------------ wiring
    builder = StateGraph(AtlasState, context_schema=AtlasContext)
    builder.add_node("load_memory", load_memory)
    builder.add_node("supervisor", supervisor)          # routes via Command(goto=...)
    builder.add_node("support", support)                # subgraph, shared schema
    builder.add_node("analyst", analyst)                # subgraph, shared schema
    builder.add_node("researcher", researcher)          # wraps subgraph w/ private schema
    builder.add_node("respond", respond)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "supervisor")
    # Workers always report back to the supervisor.
    builder.add_edge("support", "supervisor")
    builder.add_edge("analyst", "supervisor")
    builder.add_edge("researcher", "supervisor")
    builder.add_edge("respond", END)

    graph = builder.compile(
        checkpointer=checkpointer,
        store=store,
        cache=InMemoryCache(),  # backs the CachePolicy on the research planner
        name="atlas",
    )
    return graph, research_graph
