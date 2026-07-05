"""The research team: a subgraph with a *private* schema and Send map-reduce.

Flow inside the subgraph:

    plan ──(Send per subtopic)──▶ research_subtopic ×N (parallel) ──▶ synthesize

- `plan` asks the model to decompose the question into 2-4 subtopics.
- Each `Send` carries its own per-branch state (`SubtopicState`).
- Branch results land in `notes` via the `operator.add` reducer (fan-in).
- `synthesize` writes the final summary; its tokens stream to the client.
- Progress events are emitted with `get_stream_writer()` (custom stream mode).

The parent graph has a different schema (`AtlasState`), so the subgraph is
wrapped in a node function that translates between the two schemas —
subgraph integration pattern #2.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.cache.memory import InMemoryCache
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy, RetryPolicy, Send
from pydantic import BaseModel, Field

from atlas import data
from atlas.state import AtlasState, ResearchInput, ResearchOutput, ResearchState, SubtopicState


class ResearchPlan(BaseModel):
    """Decomposition of a research question."""

    subtopics: list[str] = Field(description="2-4 focused sub-questions to research in parallel.")


def build_research_graph(model: BaseChatModel):
    planner = model.with_structured_output(ResearchPlan)

    def plan(state: ResearchState):
        result: ResearchPlan = planner.invoke(
            [
                SystemMessage(
                    content="Decompose the user's question into 2-4 focused sub-questions "
                    "that can be researched independently against a product knowledge base."
                ),
                HumanMessage(content=state["topic"]),
            ]
        )
        writer = get_stream_writer()
        writer({"event": "research_plan", "subtopics": result.subtopics})
        return {"subtopics": result.subtopics[:4]}

    def fan_out(state: ResearchState):
        # Map step: one Send per subtopic → parallel branches in the same super-step.
        return [
            Send("research_subtopic", {"topic": state["topic"], "subtopic": sub})
            for sub in state["subtopics"]
        ]

    def research_subtopic(state: SubtopicState):
        writer = get_stream_writer()
        writer({"event": "researching", "subtopic": state["subtopic"]})
        docs = data.search_kb(state["subtopic"], limit=2)
        if not docs:
            note = f"[{state['subtopic']}] No knowledge-base coverage found."
        else:
            digest = model.invoke(
                [
                    SystemMessage(
                        content="Extract only the facts relevant to the sub-question from the "
                        "documents. Two sentences maximum. Cite the doc title in brackets."
                    ),
                    HumanMessage(
                        content=f"Sub-question: {state['subtopic']}\n\nDocuments:\n"
                        + "\n\n".join(f"# {d['title']}\n{d['body']}" for d in docs)
                    ),
                ]
            )
            note = f"[{state['subtopic']}] {digest.content}"
        # Reduce step: appended to `notes` by the operator.add reducer.
        return {"notes": [note]}

    def synthesize(state: ResearchState):
        answer = model.invoke(
            [
                SystemMessage(
                    content="Write a crisp, well-organized research summary that answers the "
                    "topic using ONLY the notes provided. Keep it under 180 words."
                ),
                HumanMessage(
                    content=f"Topic: {state['topic']}\n\nNotes:\n" + "\n".join(state["notes"])
                ),
            ]
        )
        return {"summary": answer.content}

    builder = StateGraph(ResearchState, input_schema=ResearchInput, output_schema=ResearchOutput)
    # Cache the plan: identical topics within the TTL skip the planning LLM call.
    builder.add_node("plan", plan, cache_policy=CachePolicy(ttl=300))
    builder.add_node(
        "research_subtopic",
        research_subtopic,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.5),
    )
    builder.add_node("synthesize", synthesize)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", fan_out, ["research_subtopic"])
    builder.add_edge("research_subtopic", "synthesize")
    builder.add_edge("synthesize", END)
    return builder.compile(name="research_team", cache=InMemoryCache())


def make_researcher_node(model: BaseChatModel):
    """Wrap the subgraph so it plugs into the parent's different schema."""
    research_graph = build_research_graph(model)

    def researcher(state: AtlasState):
        # Parent → subgraph: the latest human message becomes the research topic.
        topic = next(
            (m.content for m in reversed(state["messages"]) if m.type == "human"),
            state["messages"][-1].content,
        )
        result = research_graph.invoke({"topic": topic})
        # Subgraph → parent: summary becomes an agent message, notes accumulate.
        report = AIMessage(content=f"Research findings:\n{result['summary']}", name="researcher")
        return {
            "messages": [report],
            "research_notes": result["notes"],
            "visited": [*(state.get("visited") or []), "researcher"],
        }

    return researcher, research_graph
