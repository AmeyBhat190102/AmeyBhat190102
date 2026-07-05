"""Time travel demo: replay and fork a conversation from an earlier checkpoint.

Every super-step is checkpointed, so you can:
1. list the full checkpoint history of a thread,
2. re-run from any past checkpoint (replay),
3. edit state at that point with `update_state` and fork an alternate future.

Run:  python scripts/time_travel_demo.py   (requires ANTHROPIC_API_KEY)
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from atlas.config import AtlasContext
from atlas.graph import build_graph
from atlas.memory import seed_demo_memories


def main() -> None:
    store = InMemoryStore()
    seed_demo_memories(store)
    graph, _ = build_graph(checkpointer=InMemorySaver(), store=store)

    config = {"configurable": {"thread_id": "tt-demo"}}
    context = AtlasContext(customer_id="cus_002")

    # ---- 1. run a turn -----------------------------------------------------
    graph.invoke(
        {"messages": [HumanMessage(content="How much have I spent with you in total?")]},
        config,
        context=context,
    )
    print("=== final answer ===")
    print(graph.get_state(config).values["messages"][-1].content, "\n")

    # ---- 2. inspect checkpoint history ------------------------------------
    print("=== checkpoint history (newest first) ===")
    history = list(graph.get_state_history(config))
    for snap in history:
        print(
            f"step={snap.metadata.get('step'):>3}  "
            f"next={list(snap.next) or ['<end>']}  "
            f"checkpoint_id={snap.config['configurable']['checkpoint_id']}"
        )

    # ---- 3. pick the checkpoint right before the supervisor ran -----------
    before_supervisor = next(s for s in history if s.next and s.next[0] == "supervisor")
    print("\nForking from checkpoint where next =", before_supervisor.next)

    # ---- 4. edit history: replace the user's question ----------------------
    forked_config = graph.update_state(
        before_supervisor.config,
        {"messages": [HumanMessage(content="Which product earns the most revenue overall?")]},
    )

    # ---- 5. resume from the fork: pass None to continue from stored state --
    graph.invoke(None, forked_config, context=context)
    print("\n=== forked answer ===")
    print(graph.get_state(config).values["messages"][-1].content)


if __name__ == "__main__":
    main()
