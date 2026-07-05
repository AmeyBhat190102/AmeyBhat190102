"""Terminal chat client for Atlas with live streaming.

Shows the same streaming pipeline as the HTTP server, but synchronously:
- routing decisions and worker activity as they happen (updates mode)
- research progress events                            (custom mode)
- the final answer token-by-token                     (messages mode)
- human-in-the-loop refund approvals inline           (interrupt / resume)

Run:  python -m atlas.cli            (requires ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import sys
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from atlas.config import AtlasContext
from atlas.graph import build_graph
from atlas.memory import seed_demo_memories
from atlas.server import _chunk_text  # same chunk-text helper


def stream_turn(graph, run_input, config, context) -> list:
    """Stream one run; return any interrupts that paused it."""
    pending_interrupts = []
    printing_final = False

    for namespace, mode, payload in graph.stream(
        run_input,
        config,
        context=context,
        stream_mode=["updates", "messages", "custom"],
        subgraphs=True,
    ):
        if mode == "updates":
            for node, update in (payload or {}).items():
                if node == "__interrupt__":
                    pending_interrupts.extend(update)
                elif node == "supervisor" and isinstance(update, dict):
                    print(
                        f"\n\033[90m[supervisor → {update.get('next_agent')}] "
                        f"{update.get('routing_reason', '')}\033[0m"
                    )
                elif node in ("support", "analyst", "researcher"):
                    print(f"\033[90m[{node} finished]\033[0m")

        elif mode == "custom":
            print(f"\033[36m  ⚙ {payload}\033[0m")

        elif mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") == "respond":
                text = _chunk_text(chunk)
                if text:
                    if not printing_final:
                        print("\n\033[1mAtlas:\033[0m ", end="")
                        printing_final = True
                    print(text, end="", flush=True)

    if printing_final:
        print()
    return pending_interrupts


def main() -> None:
    graph, _ = build_graph(checkpointer=InMemorySaver(), store=InMemoryStore())
    seed_demo_memories(graph.store)

    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}
    context = AtlasContext(customer_id="cus_001")

    print(f"Atlas CLI — thread {thread_id}. Customer cus_001 (Priya). Ctrl-C to exit.")
    print("Try: 'I want a refund for my Nimbus X1 headphones, they drain battery fast.'\n")

    while True:
        try:
            user = input("\033[1mYou:\033[0m ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nbye!")
            sys.exit(0)
        if not user:
            continue

        run_input = {"messages": [{"role": "user", "content": user}]}
        interrupts = stream_turn(graph, run_input, config, context)

        # Human-in-the-loop: resolve any pause inline, then resume the run.
        while interrupts:
            payload = interrupts[0].value
            print(f"\n\033[33m⏸  HUMAN APPROVAL NEEDED: {payload.get('question')}\033[0m")
            print(f"   order={payload.get('order_id')} amount=${payload.get('amount')}")
            answer = input("   approve? [y/N] ").strip().lower()
            note = input("   note (optional): ").strip()
            resume = Command(resume={"approved": answer == "y", "note": note})
            interrupts = stream_turn(graph, resume, config, context)


if __name__ == "__main__":
    main()
