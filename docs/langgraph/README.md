# LangGraph Documentation Set

Welcome. This directory is a comprehensive, self-contained guide to **LangGraph** (Python, v1.x) — from your first `StateGraph` to production deployments with human-in-the-loop review and multi-agent orchestration.

## What is LangGraph?

LangGraph is a low-level orchestration framework for building stateful, long-running LLM applications. Instead of chaining prompts together linearly, you model your application as a **graph**: nodes do work (call a model, run a tool, transform data), edges decide what runs next, and a shared **state** object flows through everything. On top of that core, LangGraph adds durable execution (checkpointing), streaming, human-in-the-loop interrupts, and first-class support for agents and multi-agent systems. It powers agents in production at companies like Uber, LinkedIn, and Klarna, and it is the foundation under `create_react_agent` and the LangGraph Platform.

You bring the LLM (these docs use Anthropic Claude via `langchain-anthropic` throughout); LangGraph brings the control flow, persistence, and operational machinery.

## Files in this set

| # | File | What it covers |
|---|------|----------------|
| 01 | [Core concepts](01-core-concepts.md) | Why LangGraph, graphs/nodes/edges/state, the Pregel execution model, ecosystem map, hello world |
| 02 | [State management](02-state-management.md) | State schemas (TypedDict/Pydantic/dataclass), reducers, `add_messages`, input/output/private schemas, pitfalls |
| 03 | [Graph API](03-graph-api.md) | `StateGraph` in depth: nodes, edges, conditional routing, `Command`, `Send`, compile options, runtime context |
| 04 | [Streaming](04-streaming.md) | Stream modes (`values`, `updates`, `messages`, `custom`, `debug`), token streaming, custom writers |
| 05 | [Persistence & memory](05-persistence-and-memory.md) | Checkpointers, threads, time travel, long-term memory with stores |
| 06 | [Human-in-the-loop](06-human-in-the-loop.md) | `interrupt()`, `Command(resume=...)`, approval/edit/review patterns, breakpoints |
| 07 | [Tools & agents](07-tools-and-agents.md) | Tool definitions, `ToolNode`, `tools_condition`, ReAct agents, prebuilt agents |
| 08 | [Multi-agent systems](08-multi-agent-systems.md) | Supervisor, swarm, and hierarchical patterns; handoffs with `Command` |
| 09 | [Subgraphs](09-subgraphs.md) | Composing graphs, shared vs. transformed state, subgraph streaming and persistence |
| 10 | [Functional API](10-functional-api.md) | `@entrypoint` and `@task` as an alternative to the Graph API |
| 11 | [Reliability](11-reliability.md) | Retries, `RetryPolicy`, `CachePolicy`, durability modes, error handling |
| 12 | [Platform & deployment](12-platform-and-deployment.md) | LangGraph Server, Studio, CLI, self-hosted vs. cloud deployment |
| 13 | [Glossary](13-glossary.md) | Quick definitions of every term used across the set |

## Suggested learning path

1. **Foundations (start here).** Read [01 — Core concepts](01-core-concepts.md), [02 — State management](02-state-management.md), and [03 — Graph API](03-graph-api.md) in order. After these three you can build and run real graphs.
2. **Make it feel alive.** [04 — Streaming](04-streaming.md) for responsive UIs, then [05 — Persistence & memory](05-persistence-and-memory.md) for conversations that survive restarts. Persistence is the hinge of the whole framework — most advanced features depend on it.
3. **Put a human in the loop.** [06 — Human-in-the-loop](06-human-in-the-loop.md) builds directly on persistence: pause a graph mid-run, wait for approval, resume.
4. **Agents and beyond.** [07 — Tools & agents](07-tools-and-agents.md), then [08 — Multi-agent systems](08-multi-agent-systems.md) and [09 — Subgraphs](09-subgraphs.md) for larger architectures. Skim [10 — Functional API](10-functional-api.md) to know the alternative style exists.
5. **Production.** [11 — Reliability](11-reliability.md) and [12 — Platform & deployment](12-platform-and-deployment.md). Keep [13 — Glossary](13-glossary.md) open as a reference throughout.

If you only have one hour: read 01, skim 02, work through the examples in 03.

## Concept-to-file lookup

| If you're looking for... | Go to |
|---|---|
| Nodes, edges, super-steps, Pregel model | [01-core-concepts.md](01-core-concepts.md) |
| `TypedDict` vs Pydantic state, reducers, `Annotated` | [02-state-management.md](02-state-management.md) |
| `add_messages`, `MessagesState`, `RemoveMessage` | [02-state-management.md](02-state-management.md) |
| `add_node`, `add_edge`, `add_conditional_edges` | [03-graph-api.md](03-graph-api.md) |
| `Command(goto=...)`, `Send`, map-reduce fan-out | [03-graph-api.md](03-graph-api.md) |
| `recursion_limit`, `GraphRecursionError` | [03-graph-api.md](03-graph-api.md) |
| `context_schema`, `Runtime`, `config["configurable"]` | [03-graph-api.md](03-graph-api.md) |
| `stream_mode`, token streaming, `get_stream_writer` | [04-streaming.md](04-streaming.md) |
| Checkpointers, `thread_id`, time travel, `InMemorySaver` | [05-persistence-and-memory.md](05-persistence-and-memory.md) |
| Long-term memory, `InMemoryStore`, semantic search | [05-persistence-and-memory.md](05-persistence-and-memory.md) |
| `interrupt()`, `Command(resume=...)`, approvals | [06-human-in-the-loop.md](06-human-in-the-loop.md) |
| `@tool`, `ToolNode`, `tools_condition`, ReAct loops | [07-tools-and-agents.md](07-tools-and-agents.md) |
| Supervisor/swarm patterns, agent handoffs | [08-multi-agent-systems.md](08-multi-agent-systems.md) |
| Nesting graphs, `Command(graph=Command.PARENT)` | [09-subgraphs.md](09-subgraphs.md), [08-multi-agent-systems.md](08-multi-agent-systems.md) |
| `@entrypoint`, `@task` | [10-functional-api.md](10-functional-api.md) |
| `RetryPolicy`, `CachePolicy`, durability, idempotency | [11-reliability.md](11-reliability.md) |
| `langgraph.json`, LangGraph Server/Studio/CLI, deploys | [12-platform-and-deployment.md](12-platform-and-deployment.md) |
| "What does that word mean?" | [13-glossary.md](13-glossary.md) |

## Conventions used throughout

- **LangGraph v1.x, Python.** Where v0.x behaved differently, files include a short "Version note".
- **All LLM examples use Anthropic Claude** via `from langchain_anthropic import ChatAnthropic` with `llm = ChatAnthropic(model="claude-opus-4-8")`.
- Canonical imports are used consistently, e.g. `from langgraph.graph import StateGraph, START, END, MessagesState` and `from langgraph.types import Command, Send, interrupt`.
- Every code snippet is self-contained: copy it into a file, `pip install -U langgraph langchain-anthropic`, set `ANTHROPIC_API_KEY`, and run it.

## Companion project

Theory is better with practice. The companion project, **Atlas**, lives at [`../../project/atlas/`](../../project/atlas/) and applies the patterns from these docs in a working codebase — a multi-node LangGraph application with streaming, checkpointing, and human-in-the-loop review. As you finish each doc, look for the corresponding module in Atlas to see the concept used in context.

## Key takeaways

- LangGraph models LLM applications as graphs: nodes do work, edges route, state is shared memory.
- Read files 01–03 first; they are the foundation everything else builds on.
- Persistence (file 05) unlocks most advanced features: human-in-the-loop, time travel, memory.
- All examples target LangGraph v1.x with Anthropic Claude models.
- Use the lookup table above to jump straight to a concept; use the glossary when a term is unfamiliar.

## Next

Start with [01 — Core concepts](01-core-concepts.md).
