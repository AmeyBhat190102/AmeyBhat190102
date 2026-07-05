# 4. Streaming

Agents are slow: an LLM call takes seconds, a multi-step agent takes tens of seconds, and a deep research graph can run for minutes. Streaming is what turns that dead time into a live experience — tokens appearing as the model thinks, progress messages as tools run, state updates as each node finishes. LangGraph treats streaming as a first-class citizen: every compiled graph exposes `.stream()` / `.astream()` with several *stream modes* that emit different views of the same execution, and you can combine them, filter them, tunnel them out of subgraphs, and forward them over HTTP. This is the deepest chapter in this set; it covers every mode, the metadata you get with each chunk, and the operational caveats you will hit in production.

## Why streaming matters for agent UX

Three distinct things users want to *watch*, and each maps to a stream mode:

1. **Workflow progress** — "which step is the agent on?" → `updates` (or `values`).
2. **LLM tokens** — the classic typewriter effect → `messages`.
3. **Arbitrary signals** — tool progress bars, row counts, intermediate results → `custom`.

A fourth consumer is *you*, the developer: the `debug` mode emits a full execution trace for troubleshooting.

Perceived latency is the real metric. An agent that streams its first token in 400 ms *feels* faster than one that returns a perfect answer in 6 s, even if total wall time is identical. Streaming also enables early cancellation (the user sees the agent going down the wrong path and stops it) and progressive rendering (show the plan while the execution is still running).

## The `.stream()` and `.astream()` APIs

Every compiled graph (`CompiledStateGraph`) has:

```python
graph.stream(input, config=None, *, stream_mode="updates", subgraphs=False, ...)   # sync generator
graph.astream(input, config=None, *, stream_mode="updates", subgraphs=False, ...)  # async generator
```

- `input` — the same input you would pass to `invoke` (a state dict, or `Command(resume=...)` when resuming).
- `stream_mode` — a single mode string, or a list of modes.
- `subgraphs=True` — also surface chunks produced inside subgraphs, namespaced.
- The return value is a generator: iterate it to drive execution. **The graph does not run until you consume the generator.**

Here is the running example graph used throughout this file:

```python
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState

llm = ChatAnthropic(model="claude-opus-4-8")


class State(MessagesState):
    topic: str
    joke: str


def refine_topic(state: State):
    return {"topic": state["topic"] + " and cats"}


def generate_joke(state: State):
    msg = llm.invoke(f"Tell a short joke about {state['topic']}")
    return {"joke": msg.content, "messages": [msg]}


graph = (
    StateGraph(State)
    .add_node("refine_topic", refine_topic)
    .add_node("generate_joke", generate_joke)
    .add_edge(START, "refine_topic")
    .add_edge("refine_topic", "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)
```

> **Version note.** In v0.x the default `stream_mode` for `.stream()` was `"values"`; in v1.x it is `"updates"`. Pin the mode explicitly rather than relying on the default.

## Stream mode: `values` — full state after each super-step

`values` emits the **entire state** after every super-step (including the initial input). Use it when the consumer wants a self-contained snapshot each time — e.g., re-rendering a whole UI panel from scratch.

```python
for chunk in graph.stream({"topic": "ice cream", "messages": []}, stream_mode="values"):
    print(chunk)
```

Sample output (abridged):

```text
{'topic': 'ice cream', 'messages': []}
{'topic': 'ice cream and cats', 'messages': []}
{'topic': 'ice cream and cats', 'messages': [AIMessage(...)], 'joke': 'Why did the cat...'}
```

Each chunk is a plain dict shaped like your state schema. There is no node attribution — if you need to know *who* changed what, use `updates`.

## Stream mode: `updates` — per-node deltas

`updates` emits only what each node **returned**, keyed by node name. One chunk per node completion per super-step:

```python
for chunk in graph.stream({"topic": "ice cream", "messages": []}, stream_mode="updates"):
    print(chunk)
```

```text
{'refine_topic': {'topic': 'ice cream and cats'}}
{'generate_joke': {'joke': 'Why did the cat...', 'messages': [AIMessage(...)]}}
```

Notes:

- If two nodes run in the same super-step (parallel fan-out), you get **separate chunks**, one per node, within that step.
- The value is the node's raw return (the *delta*), **before** reducers merge it into state. For a `messages` channel with `add_messages`, the chunk contains only the new messages.
- Interrupts also surface here (see [Streaming and interrupts](#streaming-and-interrupts)).

`updates` is the workhorse mode for progress UIs: map node names to human-readable step labels ("Searching…", "Drafting…") and advance a stepper as chunks arrive.

## Stream mode: `messages` — LLM token streaming

`messages` emits LLM tokens from **any chat model called anywhere inside the graph** (nodes, tools, subgraphs), as 2-tuples:

```python
for message_chunk, metadata in graph.stream(
    {"topic": "ice cream", "messages": []},
    stream_mode="messages",
):
    if message_chunk.content:
        print(message_chunk.content, end="", flush=True)
```

- `message_chunk` is an `AIMessageChunk` (a LangChain message chunk — it has `.content`, `.tool_call_chunks`, etc.). Chunks are additive: `chunk1 + chunk2` concatenates content.
- `metadata` is a dict describing *where* the token came from.

### The metadata dict

Typical contents:

```python
{
    "langgraph_node": "generate_joke",      # the node that made the LLM call
    "langgraph_step": 2,                    # super-step index
    "langgraph_path": ("__pregel_pull", "generate_joke"),
    "langgraph_triggers": ("branch:to:generate_joke",),
    "checkpoint_ns": "generate_joke:<uuid>",# namespace (nested for subgraphs)
    "ls_provider": "anthropic",             # LLM provider info
    "ls_model_name": "claude-opus-4-8",
    "tags": ["joke_llm"],                   # tags set on the model/invocation
    # ... plus any run metadata
}
```

The two fields you will filter on constantly:

- **`langgraph_node`** — which node produced the token.
- **`tags`** — arbitrary labels you attach to a model.

### Filtering tokens by node

Stream only the final-answer node and hide internal chain-of-thought calls:

```python
for chunk, metadata in graph.stream(inputs, stream_mode="messages"):
    if metadata.get("langgraph_node") == "generate_joke" and chunk.content:
        print(chunk.content, end="", flush=True)
```

### Filtering tokens by LLM tags

When one node calls **multiple models**, node-level filtering is not enough. Tag each model:

```python
from langchain_anthropic import ChatAnthropic

joke_llm = ChatAnthropic(model="claude-opus-4-8", tags=["joke"])
poem_llm = ChatAnthropic(model="claude-opus-4-8", tags=["poem"])


def creative_node(state: State):
    joke = joke_llm.invoke(f"Joke about {state['topic']}")
    poem = poem_llm.invoke(f"Poem about {state['topic']}")
    return {"joke": joke.content, "messages": [joke, poem]}
```

```python
for chunk, metadata in graph.stream(inputs, stream_mode="messages"):
    if "joke" in (metadata.get("tags") or []):
        print(chunk.content, end="", flush=True)
```

Tags can also be passed per-invocation: `llm.invoke(prompt, config={"tags": ["draft"]})`.

## Stream mode: `custom` — arbitrary data from inside nodes and tools

`custom` lets **your code** emit anything mid-execution via a *stream writer*. This is how you build tool progress bars, emit partial results from a long scan, or report which URL a crawler is on:

```python
from langgraph.config import get_stream_writer


def crawl_node(state: State):
    writer = get_stream_writer()
    urls = ["https://a.example", "https://b.example", "https://c.example"]
    for i, url in enumerate(urls):
        writer({"progress": (i + 1) / len(urls), "fetching": url})
        # ... fetch url ...
    return {"topic": "crawled"}
```

```python
for chunk in graph.stream(inputs, stream_mode="custom"):
    print(chunk)
```

```text
{'progress': 0.33, 'fetching': 'https://a.example'}
{'progress': 0.67, 'fetching': 'https://b.example'}
{'progress': 1.0, 'fetching': 'https://c.example'}
```

The same works inside **tools** — a tool called by a `ToolNode` can call `get_stream_writer()` and its emissions appear in the `custom` stream:

```python
from langchain_core.tools import tool
from langgraph.config import get_stream_writer


@tool
def query_database(query: str) -> str:
    """Run a SQL query."""
    writer = get_stream_writer()
    writer({"tool": "query_database", "status": "executing", "query": query})
    rows = run_query(query)  # your DB call
    writer({"tool": "query_database", "status": "done", "rows": len(rows)})
    return str(rows)
```

Chunks can be any serializable Python object — dicts are conventional because they survive JSON transport to a frontend. If nothing consumes `stream_mode="custom"`, writer calls are cheap no-ops, so it is safe to instrument nodes unconditionally.

> **Version note.** `get_stream_writer()` was added in v0.2.x; older code received the writer as an injected `writer` parameter on the node function. Both still work, but `get_stream_writer()` is canonical in v1.x. See the [Python < 3.11 caveat](#token-streaming-and-writer-caveats) for async code.

## Stream mode: `debug` — execution trace

`debug` emits low-level trace events — one `checkpoint` event per super-step plus `task` / `task_result` events per node:

```python
for chunk in graph.stream(inputs, stream_mode="debug"):
    print(chunk["type"], chunk["step"], chunk.get("payload", {}).get("name"))
```

```text
checkpoint -1 None
checkpoint 0 None
task 1 refine_topic
task_result 1 refine_topic
checkpoint 1 None
task 2 generate_joke
task_result 2 generate_joke
checkpoint 2 None
```

Each event carries `type`, `timestamp`, `step`, and a `payload` (task id, node name, input, result, errors). Use it for building execution visualizers or diagnosing "why did this node run twice." Not intended for end-user UX.

## Streaming multiple modes at once

Pass a list, and each chunk becomes a `(mode, chunk)` tuple:

```python
for mode, chunk in graph.stream(
    {"topic": "ice cream", "messages": []},
    stream_mode=["updates", "messages", "custom"],
):
    if mode == "messages":
        token, metadata = chunk
        print("TOKEN", repr(token.content), metadata["langgraph_node"])
    elif mode == "updates":
        print("UPDATE", chunk)
    elif mode == "custom":
        print("CUSTOM", chunk)
```

This is the standard shape for real applications: one connection, demultiplexed by mode on the consumer side. The tuple wrapper appears **only** when `stream_mode` is a list (even a single-element list).

## Streaming from subgraphs

By default, a parent stream only shows the parent's own steps; a subgraph node looks like one opaque unit. Pass `subgraphs=True` to see inside. Every chunk becomes `(namespace, chunk)` — or `(namespace, mode, chunk)` with multiple modes — where `namespace` is a tuple of `"node_name:task_id"` strings describing the path:

```python
for namespace, chunk in graph.stream(inputs, stream_mode="updates", subgraphs=True):
    print(namespace, chunk)
```

```text
()                                  {'refine_topic': {...}}          # parent graph
('research:8f2c...',)               {'search': {...}}                # inside subgraph `research`
('research:8f2c...', 'rank:11ab...') {'score': {...}}                # nested two levels
```

- `()` (empty tuple) = the top-level graph.
- Namespaces nest arbitrarily deep.
- `messages` and `custom` chunks from inside subgraphs are surfaced even **without** `subgraphs=True`; what `subgraphs=True` adds is the namespace wrapper and the subgraph's `updates`/`values`/`debug` chunks.

To show only top-level progress but all tokens, stream `["updates", "messages"]` with `subgraphs=True` and drop `updates` chunks whose namespace is non-empty.

## Async streaming: `astream`

`astream` mirrors `stream` exactly with `async for`:

```python
async def run():
    async for mode, chunk in graph.astream(
        {"topic": "ice cream", "messages": []},
        stream_mode=["updates", "messages"],
    ):
        ...
```

Use `astream` in any server context (FastAPI, aiohttp) so a slow LLM does not block the event loop. Nodes may be sync or async regardless — sync nodes are dispatched to a thread pool — but async nodes calling `await llm.ainvoke(...)` stream tokens most efficiently.

## `astream_events`: fine-grained event streams

`astream_events` (v2 schema) is a LangChain-level API available on compiled graphs. Instead of graph-shaped chunks, it emits **every runnable lifecycle event** in the execution tree: `on_chain_start`, `on_chat_model_start`, `on_chat_model_stream`, `on_chat_model_end`, `on_tool_start`, `on_tool_end`, `on_retriever_end`, and so on.

```python
async for event in graph.astream_events(inputs, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        token = event["data"]["chunk"].content
        if token:
            print(token, end="", flush=True)
    elif kind == "on_tool_start":
        print(f"\n[tool {event['name']} started with {event['data'].get('input')}]")
```

Each event has `event`, `name`, `run_id`, `tags`, `metadata` (including `langgraph_node`), and `data`. You can pre-filter server-side with `include_names=`, `include_tags=`, `include_types=`.

**When to prefer `astream_events` over `stream_mode="messages"`:**

| You need | Use |
|---|---|
| Just tokens + which node/tag produced them | `stream_mode="messages"` |
| Tool start/end boundaries, retriever results, model start/end, run ids | `astream_events` |
| Interop with non-LangGraph LangChain runnables in the same pipeline | `astream_events` |
| The simplest possible consumer code | `stream()` modes |

For most agent UIs, `stream_mode=["updates", "messages", "custom"]` is enough; reach for `astream_events` when you need lifecycle boundaries that stream modes do not mark.

> **Version note.** Always pass `version="v2"`; the `v1` event schema is legacy and was the default in early v0.x.

## Token streaming and writer caveats

1. **The model must support and enable streaming.** `stream_mode="messages"` produces per-token chunks only when the underlying provider streams. `ChatAnthropic` streams by default when driven this way; if you constructed the model with `disable_streaming=True`, you will get one big chunk per call instead of tokens — the stream still works, it just is not incremental. Use `disable_streaming=True` deliberately for models/paths where streaming is unsupported (some providers reject streaming for certain tool configurations).

2. **`.invoke()` inside nodes is fine.** You do *not* need to call `llm.stream()` inside your node — LangGraph propagates a callback that captures tokens from `llm.invoke()` / `llm.ainvoke()` automatically when someone is consuming `messages` mode.

3. **Python < 3.11 + async + `get_stream_writer()`.** `get_stream_writer()` locates the writer through a `contextvars` context. On Python < 3.11, asyncio does not propagate context into tasks the way LangGraph needs, so inside **async** nodes on old Pythons `get_stream_writer()` may return a no-op. Workarounds: upgrade to Python ≥ 3.11 (recommended), or accept the writer as an injected parameter (`def my_node(state, writer):` in older versions) / pass `config` explicitly through your call chain. The same context caveat applies to token streaming from async LLM calls on < 3.11 — pass the `config` (specifically its callbacks) down to `ainvoke` manually there.

4. **No consumer, no stream.** `.stream()` returns a lazy generator. If you `list(...)` it you get everything at once at the end — the graph ran, but you buffered. Iterate incrementally.

## Serving streams over HTTP: FastAPI + SSE

Server-Sent Events (SSE) is the standard transport for one-way token streams. Using `sse-starlette` (`pip install sse-starlette`), map LangGraph modes to SSE event names:

```python
import json

from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langgraph.checkpoint.memory import InMemorySaver

app = FastAPI()
graph = builder.compile(checkpointer=InMemorySaver())  # your graph


class ChatRequest(BaseModel):
    message: str
    thread_id: str


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_generator():
        inputs = {"messages": [{"role": "user", "content": req.message}]}
        async for mode, chunk in graph.astream(
            inputs, config, stream_mode=["updates", "messages", "custom"]
        ):
            if mode == "messages":
                token, metadata = chunk
                if token.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({
                            "content": token.content,
                            "node": metadata.get("langgraph_node"),
                        }),
                    }
            elif mode == "updates":
                if "__interrupt__" in chunk:
                    intr = chunk["__interrupt__"][0]
                    yield {
                        "event": "interrupt",
                        "data": json.dumps({"id": intr.id, "value": intr.value}),
                    }
                else:
                    yield {"event": "step", "data": json.dumps(
                        {"node": next(iter(chunk))}, default=str)}
            elif mode == "custom":
                yield {"event": "progress", "data": json.dumps(chunk, default=str)}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())
```

Frontend consumption is a few lines with `EventSource` (GET) or `fetch` + a ReadableStream parser (POST, as above). Design tips:

- **One SSE event name per stream mode** (`token`, `step`, `progress`, `interrupt`, `done`) keeps client demuxing trivial.
- Always emit a terminal `done` event — SSE has no built-in "stream finished" semantics.
- Serialize with `default=str` (or a real message serializer) — `AIMessageChunk` is not directly JSON-serializable.
- Put the `thread_id` in the request so a later `/chat/resume` endpoint can resume interrupts on the same thread.

**WebSockets** are the right choice when the client also needs to talk *during* the run — live cancellation, mid-run human input without an HTTP round-trip. The producer side is identical (`async for ... graph.astream(...)` then `await websocket.send_json(...)`); you gain bidirectionality at the cost of more connection management (heartbeats, reconnect logic). For plain "watch the agent work" UIs, SSE is simpler and proxies/CDNs handle it better.

## Streaming and interrupts

When a node calls `interrupt(...)` (see [Human-in-the-loop](06-human-in-the-loop.md)), the pause is visible **in the stream** as a special `__interrupt__` update:

```python
for chunk in graph.stream(inputs, config, stream_mode="updates"):
    print(chunk)
```

```text
{'plan': {'draft': '...'}}
{'__interrupt__': (Interrupt(value={'question': 'Approve?'}, id='8b5c...'),)}
```

The generator then ends — the run is paused, checkpointed on the thread. Resume by streaming again with a `Command`:

```python
from langgraph.types import Command

for chunk in graph.stream(Command(resume=True), config, stream_mode="updates"):
    print(chunk)
```

In `values` mode the interrupt also appears under the `__interrupt__` key of the emitted snapshot. In a multi-mode stream it arrives as an `updates` chunk, which is why the SSE example above checks for it there. Frontends should treat `__interrupt__` as a signal to render an approval/input UI, keep the `thread_id`, and POST the human's answer to a resume endpoint.

## Comparison of all stream modes

| Mode | Emits | Chunk shape | Granularity | Typical use |
|---|---|---|---|---|
| `values` | Full state after each super-step | state dict | Per super-step | Re-render whole UI from a snapshot; debugging state evolution |
| `updates` | Each node's returned delta | `{node_name: delta}` | Per node completion | Progress steppers; detecting `__interrupt__`; audit of who changed what |
| `messages` | LLM tokens from any model call | `(AIMessageChunk, metadata)` | Per token | Typewriter chat UX; filter by `langgraph_node` / `tags` |
| `custom` | Whatever nodes/tools pass to `get_stream_writer()` | any object | Whenever you emit | Tool progress bars, partial results, telemetry |
| `debug` | Trace events (`checkpoint`, `task`, `task_result`) | event dict | Per scheduler event | Execution visualizers; deep troubleshooting |

Combinable: list of modes → `(mode, chunk)` tuples; `subgraphs=True` → `(namespace, ...)` prefix; `astream_events` sits alongside all of these when you need runnable-lifecycle events.

## Key takeaways

- `.stream()` / `.astream()` are lazy generators over graph execution; the default mode in v1.x is `"updates"`.
- `values` = full state per super-step; `updates` = per-node deltas keyed by node name.
- `messages` yields `(chunk, metadata)` token tuples from *any* LLM call in the graph; filter with `metadata["langgraph_node"]` or model `tags`.
- `custom` streams anything you emit via `get_stream_writer()` from nodes **or tools** — the mechanism for progress UX.
- A list of modes yields `(mode, chunk)`; `subgraphs=True` prefixes a namespace tuple; `debug` gives a full trace.
- Prefer `astream_events` (v2) only when you need lifecycle events (`on_tool_start`, `on_chat_model_end`, run ids) beyond what stream modes provide.
- Caveats: the model must actually stream (`disable_streaming=True` turns tokens into one chunk); Python < 3.11 breaks context propagation for async custom writers.
- Serve streams with FastAPI + `sse-starlette`, one SSE event name per mode, explicit `done` event; use WebSockets when the client must send mid-run.
- Interrupts appear in the stream as `__interrupt__` chunks; resume by streaming `Command(resume=...)` on the same thread — see [Persistence](05-persistence-and-memory.md) and [Human-in-the-loop](06-human-in-the-loop.md).

## Next

Continue to [5. Persistence and memory](05-persistence-and-memory.md).
