"""Atlas — a multi-agent customer support & research platform built on LangGraph.

Demonstrates, in one real-world system:
- Custom state schemas with reducers          (atlas/state.py)
- Supervisor multi-agent architecture         (atlas/agents/supervisor.py)
- ReAct agents built from StateGraph + tools  (atlas/agents/support.py, analyst.py)
- A subgraph with private state + Send map-reduce fan-out (atlas/agents/researcher.py)
- Human-in-the-loop interrupts                (atlas/tools/support_tools.py)
- Short-term memory (checkpointers) and long-term memory (Store) (atlas/graph.py, memory.py)
- Streaming: updates / messages (tokens) / custom, over SSE (atlas/server.py)
- Retry & cache policies, durability modes    (atlas/graph.py)
- The Functional API (@entrypoint / @task)    (atlas/functional_pipeline.py)
"""

__version__ = "0.1.0"
