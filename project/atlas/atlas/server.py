"""FastAPI server that exposes the Atlas graph over Server-Sent Events.

Streaming design
----------------
One graph run is streamed with THREE LangGraph stream modes at once:

- ``messages``  → LLM tokens as they are generated (with node attribution)
- ``updates``   → per-node state deltas (supervisor routing, worker results)
- ``custom``    → progress events emitted via get_stream_writer() inside nodes/tools

Each is mapped to a typed SSE event so a frontend can render tokens, an
"agent activity" timeline, and progress indicators from a single connection.

Human-in-the-loop
-----------------
When the graph hits an ``interrupt()`` (large refund approval) the stream emits
an ``interrupt`` event and ends. The client then calls ``POST /resume`` with the
decision; the run continues on the same thread from the exact paused point.

Run:  uvicorn atlas.server:app --reload
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from atlas.config import AtlasContext
from atlas.graph import build_graph
from atlas.memory import seed_demo_memories

DB_PATH = "atlas_checkpoints.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        store = InMemoryStore()
        seed_demo_memories(store)
        graph, _ = build_graph(checkpointer=checkpointer, store=store)
        app.state.graph = graph
        yield


app = FastAPI(title="Atlas — LangGraph multi-agent streaming demo", lifespan=lifespan)


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    customer_id: str = "cus_001"


class ResumeRequest(BaseModel):
    thread_id: str
    customer_id: str = "cus_001"
    approved: bool
    note: str = ""


def _chunk_text(chunk: Any) -> str:
    """Extract plain text from a message chunk (Anthropic returns block lists)."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "".join(parts)


async def _stream_run(graph, run_input, config, context) -> AsyncIterator[dict]:
    """Map LangGraph stream chunks → SSE events. Shared by /chat and /resume."""
    async for namespace, mode, payload in graph.astream(
        run_input,
        config,
        context=context,
        stream_mode=["updates", "messages", "custom"],
        subgraphs=True,          # include events from worker/research subgraphs
        durability="async",      # checkpoint without blocking the hot path
    ):
        scope = "/".join(n.split(":")[0] for n in namespace) or "atlas"

        if mode == "messages":
            chunk, metadata = payload
            text = _chunk_text(chunk)
            if not text:
                continue
            yield {
                "event": "token",
                "data": json.dumps(
                    {
                        "text": text,
                        "node": metadata.get("langgraph_node"),
                        "scope": scope,
                        # the user-facing answer comes from the `respond` node
                        "final": metadata.get("langgraph_node") == "respond",
                    }
                ),
            }

        elif mode == "updates":
            for node, update in (payload or {}).items():
                if node == "__interrupt__":
                    intr = update[0]
                    yield {
                        "event": "interrupt",
                        "data": json.dumps({"id": intr.id, "payload": intr.value}),
                    }
                    continue
                info: dict[str, Any] = {"node": node, "scope": scope}
                if isinstance(update, dict):
                    if update.get("routing_reason"):
                        info["routing_reason"] = update["routing_reason"]
                        info["next_agent"] = update.get("next_agent")
                    if update.get("messages"):
                        last = update["messages"][-1]
                        info["agent"] = getattr(last, "name", None)
                yield {"event": "update", "data": json.dumps(info)}

        elif mode == "custom":
            yield {"event": "progress", "data": json.dumps({"scope": scope, **payload})}

    yield {"event": "done", "data": "{}"}


@app.post("/chat")
async def chat(req: ChatRequest):
    graph = app.state.graph
    config = {"configurable": {"thread_id": req.thread_id}}
    run_input = {"messages": [{"role": "user", "content": req.message}]}
    context = AtlasContext(customer_id=req.customer_id)
    return EventSourceResponse(_stream_run(graph, run_input, config, context))


@app.post("/resume")
async def resume(req: ResumeRequest):
    """Resume a run paused on a human-approval interrupt."""
    graph = app.state.graph
    config = {"configurable": {"thread_id": req.thread_id}}
    state = await graph.aget_state(config)
    if not state.next:
        raise HTTPException(409, "Nothing to resume on this thread.")
    command = Command(resume={"approved": req.approved, "note": req.note})
    context = AtlasContext(customer_id=req.customer_id)
    return EventSourceResponse(_stream_run(graph, command, config, context))


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    graph = app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    interrupts = [
        {"id": i.id, "payload": i.value} for t in snapshot.tasks for i in t.interrupts
    ]
    return {
        "next": list(snapshot.next),
        "pending_interrupts": interrupts,
        "message_count": len(snapshot.values.get("messages", [])),
        "research_notes": snapshot.values.get("research_notes", []),
    }


@app.get("/history/{thread_id}")
async def get_history(thread_id: str, limit: int = 20):
    """Checkpoint history — the raw material for time travel."""
    graph = app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    history = []
    async for snap in graph.aget_state_history(config):
        history.append(
            {
                "checkpoint_id": snap.config["configurable"]["checkpoint_id"],
                "step": snap.metadata.get("step"),
                "next": list(snap.next),
                "message_count": len(snap.values.get("messages", [])),
            }
        )
        if len(history) >= limit:
            break
    return history
