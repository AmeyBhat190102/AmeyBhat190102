"""Typed project events — the studio's live narration.

Nodes emit these through LangGraph's custom stream writer; the worker
persists each one (Postgres, bigserial id = SSE id) and publishes it on
Redis. The web app's "agent theater" renders exactly this stream: agents
spawning, thumbnails appearing, the critic posting notes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "status_changed",      # project lifecycle transitions
    "brief_ready",         # intake finished
    "aura_ready",          # aura profile extracted
    "plan_created",        # producer emitted the WorkPlan
    "task_started",        # a specialist agent spawned
    "task_progress",       # free-text progress from inside a task
    "artifact_ready",      # a preview/render hit storage — thumbnail moment
    "task_finished",       # includes status + cost
    "critique",            # critic posted scores/notes for a candidate
    "revision_started",    # candidate went back to its designer
    "interrupt_raised",    # waiting on the client or the studio editor
    "interrupt_resolved",
    "budget_update",
    "package_ready",       # final gallery delivered
    "error",
]


class ProjectEvent(BaseModel):
    event_id: int | None = None            # assigned by the DB on persist
    project_id: str
    type: EventType
    task_id: str | None = None
    role_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def emit(event: ProjectEvent) -> None:
    """Emit from inside a graph node. Outside a graph run (unit tests,
    CLI without streaming) this is a silent no-op."""
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
    except Exception:
        return
    if writer is not None:
        writer(event.model_dump(mode="json"))
