"""Model factory and runtime context schema.

The runtime *context* (LangGraph v1 `context_schema`) carries per-invocation,
read-only data such as which customer is talking. It is distinct from graph
state (mutable, checkpointed) and from the long-term store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic

DEFAULT_MODEL = os.getenv("ATLAS_MODEL", "claude-opus-4-8")


@dataclass
class AtlasContext:
    """Read-only per-run context, injected into nodes via `Runtime[AtlasContext]`."""

    customer_id: str = "guest"
    model: str = DEFAULT_MODEL


def get_model(model: str | None = None, *, max_tokens: int = 2048) -> ChatAnthropic:
    """Build the chat model. Streaming is on by default for ChatAnthropic."""
    return ChatAnthropic(model=model or DEFAULT_MODEL, max_tokens=max_tokens)
