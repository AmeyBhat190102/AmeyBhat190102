"""Long-term memory helpers built on the LangGraph Store.

Short-term memory  = the checkpointer (per-thread conversation state).
Long-term memory   = the Store (cross-thread, namespaced key-value + search).
"""

from __future__ import annotations

from langgraph.store.base import BaseStore


def get_preferences(store: BaseStore, customer_id: str) -> list[str]:
    item = store.get(("preferences", customer_id), "profile")
    return list(item.value["items"]) if item else []


def seed_demo_memories(store: BaseStore) -> None:
    """Pre-load a preference so the demo shows cross-thread memory immediately."""
    store.put(
        ("preferences", "cus_001"),
        "profile",
        {"items": ["prefers concise answers", "contact by email only"]},
    )
