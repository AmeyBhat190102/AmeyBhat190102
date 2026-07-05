# 13. Glossary

A quick-reference index for every major term used in this documentation set. Each entry gives a one-line definition and links to the file that covers it in depth. Use this page when you meet an unfamiliar word mid-read, as a checklist of concepts before a code review, or as the map back into the rest of the docs. Terms are grouped alphabetically; a "common errors and fixes" table and a canonical-imports cheat sheet follow at the end.

## A–C

| Term | Definition | Covered in |
|---|---|---|
| **Agent** | A system where an LLM decides the control flow — typically a loop of model calls and tool executions until the model stops requesting tools. | [07 — Tools and agents](07-tools-and-agents.md) |
| **Assistant** | A named, versioned configuration of a deployed graph on LangGraph Platform (same graph, different prompts/config). | [12 — Platform and deployment](12-platform-and-deployment.md) |
| **Breakpoint** | A pause point in graph execution — either static (`interrupt_before`/`interrupt_after` at compile time) or dynamic (`interrupt()` in a node). | [06 — Human-in-the-loop](06-human-in-the-loop.md) |
| **Channel** | The internal storage slot behind each state key; reducers define how writes to a channel merge. | [02 — State management](02-state-management.md) |
| **Checkpoint** | A snapshot of graph state saved at a super-step boundary; the unit of persistence, resume, and time travel. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Checkpointer** | The backend that saves checkpoints per thread (`InMemorySaver`, `SqliteSaver`, `PostgresSaver`); passed to `compile(checkpointer=...)`. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Command** | A node return type (`langgraph.types.Command`) that combines a state update with a routing decision (`goto`), and the carrier for `resume` values after an interrupt. | [03 — Graph API](03-graph-api.md), [06 — Human-in-the-loop](06-human-in-the-loop.md) |
| **Conditional edge** | An edge whose destination is computed by a routing function over the current state. | [03 — Graph API](03-graph-api.md) |
| **Context schema** | Static, run-scoped configuration (user ID, model name) passed as `context=` and read via `Runtime` — separate from mutable state. | [02 — State management](02-state-management.md) |

## D–H

| Term | Definition | Covered in |
|---|---|---|
| **Durability** | How eagerly checkpoints are written during a run: `"exit"`, `"async"` (default), or `"sync"`. | [11 — Reliability](11-reliability.md) |
| **Edge** | A fixed connection declaring that one node always runs after another (`add_edge`). | [03 — Graph API](03-graph-api.md) |
| **Entrypoint** | The Functional API's workflow definition: an `@entrypoint`-decorated function with durable execution, streaming, and interrupts. | [10 — Functional API](10-functional-api.md) |
| **Fan-out / fan-in** | Running several nodes in parallel within one super-step, then merging their writes via reducers in a joining node. | [03 — Graph API](03-graph-api.md) |
| **Functional API** | The `@entrypoint`/`@task` alternative to `StateGraph`: standard Python control flow with the same runtime features. | [10 — Functional API](10-functional-api.md) |
| **Graph** | The compiled unit of execution: nodes, edges, and a state schema, run by the Pregel engine. | [01 — Core concepts](01-core-concepts.md) |
| **Handoff** | A multi-agent pattern where one agent transfers control to another, typically via a tool returning `Command(goto=..., graph=Command.PARENT)`. | [08 — Multi-agent systems](08-multi-agent-systems.md) |
| **Human-in-the-loop (HIL)** | Pausing a graph for human review, approval, or editing before continuing — built on interrupts and checkpointing. | [06 — Human-in-the-loop](06-human-in-the-loop.md) |

## I–P

| Term | Definition | Covered in |
|---|---|---|
| **Interrupt** | `interrupt(value)` pauses execution, checkpoints state, and surfaces `value` to the caller; resume with `Command(resume=...)`. | [06 — Human-in-the-loop](06-human-in-the-loop.md) |
| **Managed value** | State populated by the runtime rather than by nodes, e.g. `RemainingSteps`. | [11 — Reliability](11-reliability.md) |
| **MessagesState** | A prebuilt state schema with a `messages` key using the `add_messages` reducer. | [02 — State management](02-state-management.md) |
| **Multi-agent** | An architecture composing several agents (supervisor, swarm, hierarchical, pipeline) instead of one monolithic agent. | [08 — Multi-agent systems](08-multi-agent-systems.md) |
| **Namespace** | The hierarchical key (a tuple such as `("users", user_id)`) that organizes items in a store; also the label identifying a subgraph's position in streaming output. | [05 — Persistence and memory](05-persistence-and-memory.md), [09 — Subgraphs](09-subgraphs.md) |
| **Node** | A unit of work: a function receiving state and returning a state update (or a `Command`). | [01 — Core concepts](01-core-concepts.md) |
| **Pregel** | The bulk-synchronous-parallel execution engine underneath LangGraph; runs the plan/execute/update super-step loop. | [01 — Core concepts](01-core-concepts.md) |

## R–S

| Term | Definition | Covered in |
|---|---|---|
| **Reducer** | A function attached to a state key (via `Annotated`) that merges a new write into the existing value (e.g., append instead of overwrite). | [02 — State management](02-state-management.md) |
| **RemoveMessage** | A special message that, passed through `add_messages`, deletes the message with a matching ID (or all, via `REMOVE_ALL_MESSAGES`). | [02 — State management](02-state-management.md) |
| **Retry policy** | `RetryPolicy(max_attempts, backoff_factor, retry_on, ...)` — automatic retries for a node or task. | [11 — Reliability](11-reliability.md) |
| **Runtime** | The `langgraph.runtime.Runtime` object injected into nodes/tools, exposing `context`, `store`, and the stream writer. | [02 — State management](02-state-management.md) |
| **Send** | `Send(node, state)` dispatches a node invocation with its own private input — the mechanism behind dynamic map-reduce fan-out. | [03 — Graph API](03-graph-api.md) |
| **State** | The shared, typed data structure that flows through the graph; nodes read it and return partial updates. | [02 — State management](02-state-management.md) |
| **StateGraph** | The builder class for the Graph API: define schema, add nodes and edges, then `compile()`. | [03 — Graph API](03-graph-api.md) |
| **StateSnapshot** | The object returned by `get_state` / `get_state_history`: values, `next` nodes, config, metadata, and pending tasks at a checkpoint. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Store** | Long-term, cross-thread key-value memory (`BaseStore`, `InMemoryStore`, `PostgresStore`) organized by namespaces; supports semantic search. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Stream mode** | What `stream()` emits: `"values"`, `"updates"`, `"messages"` (LLM tokens), `"custom"`, `"debug"` — combinable as a list. | [04 — Streaming](04-streaming.md) |
| **Subgraph** | A compiled graph used as a node (or invoked inside a node) of a parent graph, communicating through shared or transformed state keys. | [09 — Subgraphs](09-subgraphs.md) |
| **Super-step** | One iteration of the Pregel loop: all ready nodes run in parallel, then their writes are applied via reducers; the checkpoint boundary. | [01 — Core concepts](01-core-concepts.md) |
| **Supervisor** | A multi-agent architecture where a central agent routes work to specialized worker agents and decides when to finish. | [08 — Multi-agent systems](08-multi-agent-systems.md) |
| **Swarm** | A decentralized multi-agent architecture where agents hand off directly to each other, and the last active agent "owns" the conversation. | [08 — Multi-agent systems](08-multi-agent-systems.md) |

## T–Z

| Term | Definition | Covered in |
|---|---|---|
| **Task** | A `@task`-decorated function in the Functional API: durable, retryable, parallelizable; returns a future (`.result()`). | [10 — Functional API](10-functional-api.md) |
| **Thread** | A sequence of checkpoints identified by `thread_id` — one conversation or workflow instance with its own history. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Time travel** | Replaying or forking a thread from a past checkpoint (`checkpoint_id` + optional `update_state`) to explore alternative paths. | [05 — Persistence and memory](05-persistence-and-memory.md) |
| **Tool** | A function (usually via `@tool`) whose schema is exposed to the LLM so the model can request calls with generated arguments. | [07 — Tools and agents](07-tools-and-agents.md) |
| **ToolNode** | The prebuilt node that executes the tool calls found in the last AI message and appends `ToolMessage` results. | [07 — Tools and agents](07-tools-and-agents.md) |

## Common errors and fixes

| Error / symptom | Cause | Fix |
|---|---|---|
| `GraphRecursionError` | The graph exceeded `recursion_limit` (default 25 super-steps) — usually a loop that never routes to `END`. | Fix the loop's exit condition; raise the limit via `config={"recursion_limit": 50}`; use `RemainingSteps` to exit gracefully. See [11 — Reliability](11-reliability.md). |
| `interrupt()` raises / graph doesn't pause | No checkpointer attached, or no `thread_id` in the config — interrupts require persistence. | Compile with a checkpointer and invoke with `{"configurable": {"thread_id": ...}}`. See [06 — Human-in-the-loop](06-human-in-the-loop.md). |
| `InvalidUpdateError: ... can only receive one value per step` | Two parallel nodes wrote the same state key that has no reducer. | Add a reducer to the key (`Annotated[list, add]` / `add_messages`), or restructure so only one node writes it per super-step. See [02 — State management](02-state-management.md). |
| Serialization error when checkpointing | State contains unserializable objects (open clients, locks, lambdas). | Keep state to plain data (dicts, lists, strings, messages, dataclasses); pass clients via context/`Runtime`, not state. See [05 — Persistence and memory](05-persistence-and-memory.md). |
| Resume starts a fresh run instead of continuing | `Command(resume=...)` (or `None` re-invoke) sent without the original `thread_id`, so there is no checkpoint to resume from. | Pass the exact same `thread_id` used for the interrupted run. See [06 — Human-in-the-loop](06-human-in-the-loop.md). |
| Same node seems to run twice after resume | Expected behavior: resuming re-executes the interrupted node from its start up to the `interrupt()` call. | Put side effects after the interrupt or in a separate node/task; make pre-interrupt effects idempotent. See [11 — Reliability](11-reliability.md). |

## Canonical imports cheat sheet

The import paths used throughout this documentation set (LangGraph v1.x):

```python
# Graph API
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages

# Control flow, HIL, and reliability primitives
from langgraph.types import Command, Send, interrupt, RetryPolicy, CachePolicy

# Persistence and memory
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# Streaming
from langgraph.config import get_stream_writer

# Functional API
from langgraph.func import entrypoint, task

# Prebuilts and runtime
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime

# Models (all examples in these docs)
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-opus-4-8")
```

> **Version note:** if you see `from langgraph.checkpoint.memory import MemorySaver` or `interrupt_before=` sprinkled through older tutorials, you are reading v0.x-era code — `MemorySaver` is now `InMemorySaver`, dynamic `interrupt()` is preferred over static breakpoints, and `retry=`/`checkpoint_during=` became `retry_policy=`/`durability=`.

## Next

Back to the [README](README.md) for the full table of contents and suggested reading paths.
