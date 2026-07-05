"""Worker agents (support, analyst) built as ReAct loops with the Graph API.

Each worker is a *subgraph that shares the parent schema* (`AtlasState`), so it
can be added to the parent graph directly as a node — integration pattern #1
from the docs. The research team (different schema) shows pattern #2.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import RetryPolicy

from atlas.state import AtlasState

SUPPORT_PROMPT = """You are Atlas Support, handling customer {customer_id}.
Known long-term preferences for this customer: {preferences}.

Use your tools to look up orders and process refunds. Never invent order data.
For refunds: check eligibility first, then call issue_refund — large refunds
automatically pause for human approval, so just call the tool.
When the user states a lasting preference, save it with remember_preference.
When you have finished the task, reply with a concise summary of what you did
(the supervisor will decide what happens next). Do not address the user directly."""

ANALYST_PROMPT = """You are Atlas Analyst. Answer analytical questions about orders,
spend and products using your tools. Current customer: {customer_id}.
Reply with the numbers and a one-line interpretation. Do not address the user
directly — your output goes back to the supervisor."""


def build_worker(
    name: str,
    model: BaseChatModel,
    tools: list[BaseTool],
    prompt_template: str,
):
    """Build a `model ⇄ tools` loop over the shared AtlasState schema."""
    bound = model.bind_tools(tools)

    def call_model(state: AtlasState):
        facts = state.get("facts") or {}
        system = prompt_template.format(
            customer_id=facts.get("customer_id", "guest"),
            preferences=facts.get("preferences") or "none on file",
        )
        response = bound.invoke([SystemMessage(content=system), *state["messages"]])
        response.name = name  # attribute the message to this agent
        return {"messages": [response]}

    def mark_visited(state: AtlasState):
        return {"visited": [*(state.get("visited") or []), name]}

    builder = StateGraph(AtlasState)
    builder.add_node(
        "model",
        call_model,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0),
    )
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("done", mark_visited)
    builder.add_edge(START, "model")
    # If the model asked for tools → run them; otherwise wrap up.
    builder.add_conditional_edges("model", tools_condition, {"tools": "tools", END: "done"})
    builder.add_edge("tools", "model")
    builder.add_edge("done", END)
    return builder.compile(name=name)
