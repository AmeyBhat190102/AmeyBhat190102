# 5. Persistence and memory

Out of the box, a compiled graph is stateless between runs: every `invoke` starts from scratch and everything is forgotten when it returns. Persistence changes that. A **checkpointer** saves a checkpoint of graph state at every super-step to a **thread**, which unlocks multi-turn conversations, pausing for human input, fault tolerance, and time travel; a **store** adds long-term memory that outlives any single thread. This chapter covers both layers, plus the practical craft of keeping message histories from growing without bound.

## Checkpointers: the concept

When you compile a graph with a checkpointer, LangGraph writes a **checkpoint** after every super-step — a snapshot of channel values, pending tasks, and metadata — appended to the history of a *thread*. A thread is just an id you choose; think "conversation" or "session".

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-42-session-1"}}
graph.invoke({"messages": [{"role": "user", "content": "hi, I'm Amey"}]}, config)
graph.invoke({"messages": [{"role": "user", "content": "what's my name?"}]}, config)
# Second call sees the first call's messages: same thread, state restored.
```

Every stateful operation — `invoke`, `stream`, `get_state`, `update_state` — requires a `thread_id` in `config["configurable"]` once a checkpointer is attached. Different `thread_id` = independent history.

> **Version note.** `InMemorySaver` was called `MemorySaver` in v0.x; the old name remains as an alias.

## Checkpointer backends

| Backend | Package | Class | Use for |
|---|---|---|---|
| In-memory | `langgraph` (built in) | `InMemorySaver` | Tests, notebooks, demos — lost on process exit |
| SQLite | `langgraph-checkpoint-sqlite` | `SqliteSaver` / `AsyncSqliteSaver` | Local apps, single-process persistence |
| Postgres | `langgraph-checkpoint-postgres` | `PostgresSaver` / `AsyncPostgresSaver` | Production |

```python
# SQLite (sync)
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    graph.invoke(inputs, {"configurable": {"thread_id": "t1"}})

# SQLite (async)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    await graph.ainvoke(inputs, {"configurable": {"thread_id": "t1"}})

# Postgres
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:pass@localhost:5432/db"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # create tables — run once
    graph = builder.compile(checkpointer=checkpointer)
```

All backends implement the same `BaseCheckpointSaver` interface, so swapping `InMemorySaver` for `PostgresSaver` is a one-line change. Community backends exist for Redis, MongoDB, and others.

## What a checkpoint contains: `StateSnapshot`

`graph.get_state(config)` returns the latest `StateSnapshot` for a thread:

```python
snapshot = graph.get_state({"configurable": {"thread_id": "t1"}})

snapshot.values      # the state dict at this checkpoint
snapshot.next        # tuple of node names to execute next (() if run finished)
snapshot.config      # config incl. this checkpoint's checkpoint_id
snapshot.metadata    # {"source": "loop", "step": 2, "writes": {...}, ...}
snapshot.created_at  # ISO timestamp
snapshot.parent_config  # config of the previous checkpoint
snapshot.tasks       # PregelTask objects: pending nodes, errors, interrupts
```

- `next` non-empty means the run is mid-flight (paused at an interrupt, or crashed).
- `tasks` carries per-task detail — including `Interrupt` objects when paused (see [Human-in-the-loop](06-human-in-the-loop.md)).

The full history, newest first:

```python
for snap in graph.get_state_history({"configurable": {"thread_id": "t1"}}):
    print(snap.config["configurable"]["checkpoint_id"], snap.metadata["step"], snap.next)
```

## `update_state`: editing a thread

You can write to a thread's state directly, without running the graph:

```python
graph.update_state(
    {"configurable": {"thread_id": "t1"}},
    {"topic": "corrected topic"},
    as_node="refine_topic",   # optional: attribute the write to a node
)
```

- The update is applied **through the reducers** — for a `messages` channel with `add_messages`, passing a message appends (or replaces by id), it does not overwrite the list.
- `as_node` makes the write behave as if that node had returned it, which determines which edges fire next. Omit it and LangGraph attributes the write to the last node that ran (erroring if ambiguous).
- Every `update_state` creates a **new checkpoint** — it forks history rather than mutating it, so you can always get back to the pre-edit snapshot.

This is the mechanism behind "edit the agent's state, then continue" HITL flows.

## Time travel: replay and fork

Every checkpoint has a `checkpoint_id`. Passing one in the config makes the graph start from *that* snapshot instead of the latest:

```python
history = list(graph.get_state_history({"configurable": {"thread_id": "t1"}}))
past = history[2]  # some earlier checkpoint

# Replay: re-run from that point on the same thread.
# Steps *before* the checkpoint are not re-executed — they are replayed from the log.
for chunk in graph.stream(None, past.config, stream_mode="updates"):
    print(chunk)

# Fork: modify the past, creating an alternative future
forked_config = graph.update_state(past.config, {"topic": "what if instead..."})
graph.invoke(None, forked_config)
```

Input `None` means "continue from the checkpoint" rather than "here is new input". Forks share the ancestry up to the branch point; `get_state_history` shows all branches. This is how you build "regenerate response" and "edit an earlier user message" features, and how you debug agents by rewinding to the step before things went wrong.

## Fault tolerance and resuming after crashes

Because a checkpoint is written each super-step, a crash (process kill, OOM, provider outage mid-run) loses at most the in-flight step. On restart, inspect and resume:

```python
snapshot = graph.get_state(config)
if snapshot.next:                 # run didn't finish
    graph.invoke(None, config)    # resume from the last good checkpoint
```

Successfully completed nodes in the failed super-step are not re-run — their writes are saved as *pending writes* and reused; only failed/unstarted tasks execute again.

## Durability modes (v0.5+ / 1.x)

`invoke` / `stream` accept a `durability` argument trading latency for safety:

```python
graph.invoke(inputs, config, durability="sync")
```

| Mode | Behavior | Use when |
|---|---|---|
| `"sync"` | Checkpoint written and confirmed before the next step starts | Maximum safety; must never lose a step |
| `"async"` (default) | Checkpoint written concurrently with the next step | Good balance for most apps |
| `"exit"` | Checkpoint written only when the run ends (or interrupts) | Cheap runs where intermediate durability is not worth the writes |

> **Version note.** Before v0.5 this was controlled by `checkpoint_during=True/False`; `durability` supersedes it.

## Short-term vs long-term memory

| | Short-term memory | Long-term memory |
|---|---|---|
| Mechanism | Checkpointer (thread state) | Store (`BaseStore`) |
| Scope | One thread | Across all threads |
| Shape | Your state schema (e.g., messages) | Namespaced JSON documents |
| Typical content | Conversation history, scratch state | User profile, preferences, learned facts |
| Lifetime | The conversation | Indefinite |

Short-term memory is simply what the checkpointer gives you: state (including message history) restored per thread. Long-term memory needs a different tool, because a fact learned on Monday's thread should be available on Tuesday's.

## The Store: cross-thread long-term memory

A `BaseStore` is a namespaced key-value (and vector) store, passed at compile time alongside the checkpointer:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
graph = builder.compile(checkpointer=InMemorySaver(), store=store)
```

Data model: **namespace** (a tuple, like a folder path) → **key** (string) → **value** (dict).

```python
namespace = ("memories", "user-42")           # scope by user id
store.put(namespace, "food", {"text": "prefers mango ice cream"})
store.put(namespace, "lang", {"text": "answers should be in English"})

item = store.get(namespace, "food")
item.value      # {'text': 'prefers mango ice cream'}
item.key, item.namespace, item.created_at, item.updated_at

results = store.search(namespace, filter={"text": {"$eq": "..."}}, limit=10)
```

### Semantic search with embeddings

Give the store an index config and `search` becomes semantic:

```python
from langchain_anthropic import ChatAnthropic  # LLM for the graph itself
from langchain.embeddings import init_embeddings
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(
    index={
        "embed": init_embeddings("voyageai:voyage-3"),  # any embeddings object/fn
        "dims": 1024,
        "fields": ["text"],       # which value fields to embed (default: whole doc)
    }
)

store.put(("memories", "user-42"), "food", {"text": "prefers mango ice cream"})
hits = store.search(("memories", "user-42"), query="what desserts do they like?", limit=3)
for hit in hits:
    print(hit.score, hit.value["text"])
```

`PostgresStore` (from `langgraph-checkpoint-postgres`) offers the same API backed by pgvector for production.

### Accessing the store inside nodes

Canonical in v1.x — `get_store()`:

```python
from langgraph.config import get_store


def personalize(state: MessagesState, config):
    store = get_store()
    user_id = config["configurable"]["user_id"]
    memories = store.search(("memories", user_id), query=state["messages"][-1].content)
    context = "\n".join(m.value["text"] for m in memories)
    msg = llm.invoke(f"Context about the user:\n{context}\n\n{state['messages'][-1].content}")
    return {"messages": [msg]}
```

Alternatively, declare a `store: BaseStore` parameter on the node (or tool) signature and LangGraph injects it. A typical **cross-thread user memory pattern**: a node extracts durable facts from the conversation and `put`s them under `("memories", user_id)`; every new thread for that user starts by `search`ing that namespace and prepending the hits to the system prompt.

## Managing long message histories

Threads accumulate messages; models have context limits and long prompts cost money. Three tools:

**Trimming (non-destructive, per-call)** — bound what you *send* to the model without touching stored state:

```python
from langchain_core.messages import trim_messages

def call_model(state: MessagesState):
    trimmed = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=llm,           # counts with the model's tokenizer
        max_tokens=4000,
        start_on="human",
        include_system=True,
    )
    return {"messages": [llm.invoke(trimmed)]}
```

**Deleting (destructive, edits state)** — `add_messages` treats `RemoveMessage` as a deletion instruction:

```python
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

def prune(state: MessagesState):
    # delete all but the last two messages
    return {"messages": [RemoveMessage(id=m.id) for m in state["messages"][:-2]]}

def reset(state: MessagesState):
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```

Be careful to keep histories valid for the provider — e.g., do not orphan a tool message from its preceding assistant tool call.

**Summarization (compress, keep meaning)** — periodically fold old messages into a running summary field:

```python
class State(MessagesState):
    summary: str

def summarize(state: State):
    prompt = (
        f"Extend this summary with the new messages:\n{state.get('summary', '')}"
        if state.get("summary") else "Summarize the conversation:"
    )
    summary = llm.invoke(state["messages"] + [{"role": "user", "content": prompt}])
    deletions = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": summary.content, "messages": deletions}
```

Route to `summarize` conditionally (e.g., when `len(state["messages"]) > 20`), and have the model-calling node prepend the summary as a system message.

## Serialization notes

- Checkpointers serialize state with `JsonPlusSerializer`, which handles LangChain messages, pydantic models, sets, datetimes, and other common types beyond plain JSON.
- Values it cannot encode fall back to **pickle** — convenient, but a smell: keep state JSON-friendly (no open connections, locks, or clients in state) so checkpoints stay portable and inspectable.
- For sensitive state, wrap serialization with `EncryptedSerializer` (`from langgraph.checkpoint.serde.encrypted import EncryptedSerializer`; with `LANGGRAPH_AES_KEY` set, `EncryptedSerializer.from_pycryptodome_aes()` gives AES-encrypted checkpoints) and pass it as the checkpointer's `serde`.

## Key takeaways

- A checkpointer saves a checkpoint per super-step to a thread; pass it to `compile(checkpointer=...)` and select the thread with `config={"configurable": {"thread_id": ...}}`.
- Use `InMemorySaver` for development, `SqliteSaver`/`AsyncSqliteSaver` locally, `PostgresSaver` in production (`.setup()` once).
- `get_state` returns a `StateSnapshot` (`values`, `next`, `config`, `metadata`, `tasks`); `get_state_history` walks all checkpoints.
- `update_state` forks a new checkpoint through the reducers; `as_node` controls which edges fire next.
- Time travel = run with a past `checkpoint_id` (replay) or `update_state` on it (fork); crashes resume with `invoke(None, config)`.
- `durability="sync" | "async" | "exit"` trades checkpoint safety against latency (v0.5+).
- Short-term memory is the thread; long-term memory is the Store: namespaces → keys → dict values, with `put`/`get`/`search` and optional embedding-backed semantic search; access in nodes via `get_store()`.
- Control history growth with `trim_messages` (per-call), `RemoveMessage`/`REMOVE_ALL_MESSAGES` (destructive), or a summarization node.

## Next

Continue to [6. Human-in-the-loop](06-human-in-the-loop.md).
