# 3. Graph API

The Graph API — `StateGraph` and everything you attach to it — is how you declare control flow in LangGraph. This file goes deep on nodes and edges, conditional routing, dynamic control with `Command` and `Send`, recursion limits, `compile()` options, execution methods, runtime configuration and context injection, visualization, and finishes with a worked example combining conditional edges, parallel branches, and map-reduce fan-out.

## Nodes: `add_node`

A node is a Python function (sync or async) registered under a name. Its first argument is the state; it returns a partial state update (see [State management](02-state-management.md)).

```python
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    text: str
    result: str


def simple(state: State) -> dict:
    return {"result": state["text"].upper()}


def with_config(state: State, config: RunnableConfig) -> dict:
    # Optional second arg: per-invocation config (thread id, tags, callbacks...)
    user = config["configurable"].get("user_id", "anonymous")
    return {"result": f"{state['text']} (for {user})"}


builder = StateGraph(State)
builder.add_node("simple", simple)              # explicit name
builder.add_node(with_config)                   # name inferred from function name
builder.add_node("aliased", with_config)        # same function, different node name
```

Rules and options worth knowing:

- Node names must be unique and can't be `"START"`/`"END"` or contain certain reserved characters.
- If you omit the name, the function's `__name__` is used.
- Besides `config`, LangGraph inspects your signature and **injects** other arguments on demand: `runtime: Runtime[Ctx]` (typed runtime context, see below), and in nodes of a store-enabled graph, the store. You only declare what you need.
- `add_node` also accepts per-node `retry_policy=RetryPolicy(...)` and `cache_policy=CachePolicy(...)` — covered in [Reliability](11-reliability.md).

## `START`, `END`, and plain edges

`START` and `END` are virtual nodes: `START` is where input enters, `END` marks completion of a path. You wire fixed transitions with `add_edge`:

```python
builder.add_edge(START, "simple")     # entry point
builder.add_edge("simple", "aliased")
builder.add_edge("aliased", END)
```

- `add_edge(START, "x")` sets the entry point. Multiple edges from `START` fan out immediately.
- `add_edge(["a", "b"], "c")` — a *list* of sources — means "run `c` only after **all** of `a` and `b` have finished" (a join/barrier for parallel branches).
- Reaching `END` on one path doesn't kill other still-active paths; the graph stops when *no* nodes remain active.

> **Version note:** v0.x had `builder.set_entry_point("x")` and `set_finish_point("x")`; in v1.x prefer explicit `add_edge(START, ...)` / `add_edge(..., END)`.

## Conditional edges: `add_conditional_edges`

A **router function** examines state and returns the name(s) of the next node(s):

```python
def route_by_length(state: State) -> str:
    return "summarize" if len(state["text"]) > 500 else "passthrough"

builder.add_conditional_edges("classify", route_by_length)
```

The router may return a single node name, a **list of names** (fan-out to all of them in the next super-step), or `END`. Two refinements:

```python
# Path map: decouples router return values from node names,
# and lets visualization know the possible targets.
builder.add_conditional_edges(
    "classify",
    route_by_length,
    {"summarize": "summarizer_node", "passthrough": "final_node"},
)

# Or annotate the router's return type for visualization without a map:
from typing import Literal

def route_by_length(state: State) -> Literal["summarize", "passthrough"]:
    ...
```

Routers should be **pure functions of state** — do the LLM call in the node *before* the router, write its decision into state, and route on that. That keeps routing replayable and cheap.

## Parallel fan-out and how updates merge

Multiple ordinary edges out of one node (or a router returning a list) activate several nodes in the **same super-step**; they run concurrently:

```python
import operator
from typing import Annotated, TypedDict


class State(TypedDict):
    topic: str
    notes: Annotated[list[str], operator.add]   # reducer required for parallel writers!


builder.add_edge(START, "plan")
builder.add_edge("plan", "search_web")     # ┐ both run in parallel
builder.add_edge("plan", "search_docs")    # ┘ in the next super-step
builder.add_edge(["search_web", "search_docs"], "combine")   # join: wait for both
```

Within a super-step, each parallel node's update is applied through the key's reducer. With `operator.add`, both nodes' `notes` land in the list (order between parallel branches is deterministic but you shouldn't depend on it). Without a reducer, two writers to the same key raise `InvalidUpdateError`. This reducer-mediated merge is *the* contract that makes fan-out safe.

## Dynamic routing from inside a node: `Command`

Sometimes the node that does the work is also the right place to decide what's next. Return a `Command` to combine a **state update and a goto** in one shot:

```python
from typing import Literal, TypedDict

from langgraph.types import Command


class State(TypedDict):
    attempts: int
    ok: bool


def validate(state: State) -> Command[Literal["retry", "done"]]:
    ok = check(state)                      # your logic
    return Command(
        update={"attempts": state["attempts"] + 1, "ok": ok},
        goto="done" if ok else "retry",
    )
```

Notes:

- Type-annotate the return as `Command[Literal[...]]` so LangGraph can render the possible edges and validate the graph.
- `goto` accepts a node name, `END`, or a list of targets (fan-out). No `add_edge` from `validate` is needed for targets declared this way.
- Use `Command` when update-and-route belong together; use conditional edges when routing is a separate, stateless decision. Don't use both for the same transition.
- In multi-agent systems, `Command(goto="other_agent", graph=Command.PARENT)` lets a node in a subgraph hand control to a sibling in the **parent** graph — the core handoff mechanism. Brief mention only; see [Multi-agent systems](08-multi-agent-systems.md).
- `Command(resume=...)` is how you resume from an `interrupt()` — see [Human-in-the-loop](06-human-in-the-loop.md).

## Map-reduce fan-out: the `Send` API

Ordinary edges fan out to *different nodes*, each seeing the same state. `Send` fans out to **N dynamic copies of the same node, each with its own private input** — the map step of map-reduce, where N isn't known until runtime:

```python
import operator
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

llm = ChatAnthropic(model="claude-opus-4-8")


class State(TypedDict):
    topic: str
    subtopics: list[str]
    sections: Annotated[list[str], operator.add]    # reduce step accumulates here


class SectionState(TypedDict):      # per-branch state: NOT the graph state
    subtopic: str


def plan(state: State) -> dict:
    resp = llm.invoke(f"List 3 subtopics of {state['topic']}, one per line.")
    return {"subtopics": [s.strip() for s in resp.content.splitlines() if s.strip()]}


def fan_out(state: State) -> list[Send]:
    # Router returning Send objects: one branch per subtopic
    return [Send("write_section", {"subtopic": s}) for s in state["subtopics"]]


def write_section(state: SectionState) -> dict:
    resp = llm.invoke(f"Write two sentences about {state['subtopic']}.")
    return {"sections": [resp.content]}             # reducer merges all branches


builder = StateGraph(State)
builder.add_node("plan", plan)
builder.add_node("write_section", write_section)
builder.add_edge(START, "plan")
builder.add_conditional_edges("plan", fan_out, ["write_section"])
builder.add_edge("write_section", END)
graph = builder.compile()
```

Key properties: the dict you pass to `Send(node, arg)` is delivered *as that branch's state* (so the worker node can use a different, smaller schema); all branches run in parallel in one super-step; their updates merge back into the real graph state via reducers. Nodes can also return `Send` objects inside `Command(goto=[Send(...), ...])`.

## Recursion limit and `GraphRecursionError`

Each super-step counts against a **recursion limit** (default 25). A cyclic graph that never routes to `END` will hit it and raise `GraphRecursionError` — your safety net against infinite agent loops:

```python
from langgraph.errors import GraphRecursionError

try:
    graph.invoke(inputs, config={"recursion_limit": 100})   # raise the ceiling per-run
except GraphRecursionError:
    print("Graph exceeded 100 super-steps — likely stuck in a loop.")
```

The limit is set in the config dict (top-level key, *not* inside `configurable`) and resets per invocation. If you routinely raise it past a few hundred, reconsider the design — or track a counter in state and route to `END` gracefully.

## `compile()` options

`compile()` validates the structure and returns the runnable graph:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

graph = builder.compile(
    checkpointer=InMemorySaver(),   # durable state across invocations → 05
    store=InMemoryStore(),          # cross-thread long-term memory → 05
    interrupt_before=["tools"],     # static breakpoints before these nodes → 06
    interrupt_after=[],             # ...or after
    name="atlas-researcher",        # shows up in traces & when used as a subgraph
    cache=None,                     # cache backend for CachePolicy-enabled nodes → 11
)
```

| Option | Purpose | Details in |
|---|---|---|
| `checkpointer` | Save state at every super-step; enables threads, resume, time travel, HITL | [05](05-persistence-and-memory.md) |
| `store` | Long-term key-value/semantic memory shared across threads | [05](05-persistence-and-memory.md) |
| `interrupt_before` / `interrupt_after` | Static breakpoints for debugging/approval | [06](06-human-in-the-loop.md) |
| `name` | Graph name for tracing and subgraph display | [09](09-subgraphs.md) |
| `cache` | Backend for node-level `CachePolicy` | [11](11-reliability.md) |

## Running a graph: invoke / stream / batch

Compiled graphs implement the Runnable interface:

```python
result = graph.invoke({"topic": "caching"}, config)          # run to completion, final state
result = await graph.ainvoke({"topic": "caching"}, config)   # async variant

for chunk in graph.stream({"topic": "caching"}, config, stream_mode="updates"):
    print(chunk)                                             # progressive output → 04

async for chunk in graph.astream({"topic": "caching"}, config, stream_mode="messages"):
    ...

results = graph.batch([{"topic": "a"}, {"topic": "b"}])      # parallel over inputs
```

`stream`/`astream` and the various `stream_mode`s deserve their own file: [Streaming](04-streaming.md).

## Runtime configuration and context

### The classic way: `config["configurable"]`

Anything you put under `configurable` rides along the whole run and is readable in any node via the `config` argument:

```python
config = {"configurable": {"thread_id": "thread-1", "user_id": "u42"}}
graph.invoke({"topic": "x"}, config)
```

`thread_id` (for checkpointing) lives here. For your *own* dependencies, v1.x offers something better:

### v0.6+ typed context: `context_schema` and `Runtime`

Declare a dataclass of immutable per-run dependencies, pass it at invoke time via `context=`, and receive it in nodes as an injected, fully-typed `Runtime`:

```python
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.runtime import Runtime


@dataclass
class Ctx:
    user_name: str
    model_name: str = "claude-opus-4-8"


def chat(state: MessagesState, runtime: Runtime[Ctx]) -> dict:
    llm = ChatAnthropic(model=runtime.context.model_name)
    system = f"Address the user as {runtime.context.user_name}."
    resp = llm.invoke([{"role": "system", "content": system}, *state["messages"]])
    return {"messages": [resp]}


builder = StateGraph(MessagesState, context_schema=Ctx)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)
graph = builder.compile()

graph.invoke(
    {"messages": [{"role": "user", "content": "hello"}]},
    context=Ctx(user_name="Amey"),
)
```

`Runtime` also exposes `runtime.store`, `runtime.stream_writer`, and `runtime.previous` (Functional API). In code that isn't a node signature — e.g., inside a tool — grab it with `get_runtime`:

```python
from langgraph.runtime import get_runtime

def some_tool_helper() -> str:
    runtime = get_runtime(Ctx)
    return runtime.context.user_name
```

> **Version note:** Before v0.6 this was `StateGraph(State, config_schema=MySchema)` with values passed inside `config["configurable"]`. `context_schema`/`context=`/`Runtime` supersede that pattern in v1.x; `configurable` remains for run identity (`thread_id`) and backward compatibility.

## Visualization

Every compiled graph can render itself — invaluable for reviewing control flow:

```python
print(graph.get_graph().draw_mermaid())        # Mermaid source, paste anywhere
png_bytes = graph.get_graph().draw_mermaid_png()   # rendered image
print(graph.get_graph().draw_ascii())          # quick terminal view
```

Use `graph.get_graph(xray=True)` to expand subgraphs in the drawing. Conditional edges render as dashed lines when LangGraph can infer targets (path map or `Literal`/`Command` annotations — another reason to annotate).

## Async nodes

Define nodes with `async def` when they await I/O (LLM calls, HTTP, DB). Mix sync and async freely; run the graph with `ainvoke`/`astream` to get real concurrency for parallel async branches:

```python
async def fetch(state: State) -> dict:
    resp = await llm.ainvoke(f"Summarize: {state['text']}")
    return {"result": resp.content}
```

Sync nodes inside an async run are executed in a thread pool, so they don't block the event loop — but prefer `async def` for anything I/O-bound in async apps.

## Worked example: conditional edges + parallel branches + Send

A mini research pipeline: classify the request; trivial ones get a direct answer; substantial ones fan out to two fixed researchers in parallel *and* a dynamic `Send`-based fan-out over subtopics; everything joins in a final writer.

```python
import operator
from typing import Annotated, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

llm = ChatAnthropic(model="claude-opus-4-8")


class State(TypedDict):
    question: str
    complexity: str
    subtopics: list[str]
    findings: Annotated[list[str], operator.add]
    answer: str


class SubtopicState(TypedDict):
    subtopic: str


def classify(state: State) -> dict:
    resp = llm.invoke(
        f"Is this question 'trivial' or 'complex'? Reply with one word.\n\n{state['question']}"
    )
    label = "trivial" if "trivial" in resp.content.lower() else "complex"
    subs = []
    if label == "complex":
        plan = llm.invoke(f"List 3 subtopics to research for: {state['question']}")
        subs = [s.strip("- ").strip() for s in plan.content.splitlines() if s.strip()][:3]
    return {"complexity": label, "subtopics": subs}


def route(state: State) -> Literal["quick_answer", "fan_out"]:
    return "quick_answer" if state["complexity"] == "trivial" else "fan_out"


def quick_answer(state: State) -> dict:
    resp = llm.invoke(state["question"])
    return {"answer": resp.content}


def fan_out(state: State) -> dict:
    return {}   # pure junction node; real fan-out happens on its outgoing edges


def search_background(state: State) -> dict:           # fixed parallel branch 1
    resp = llm.invoke(f"Give background context for: {state['question']}")
    return {"findings": [f"[background] {resp.content}"]}


def search_counterpoints(state: State) -> dict:        # fixed parallel branch 2
    resp = llm.invoke(f"Give counterpoints or caveats for: {state['question']}")
    return {"findings": [f"[caveats] {resp.content}"]}


def dispatch_subtopics(state: State) -> list[Send]:    # dynamic Send fan-out
    return [Send("research_subtopic", {"subtopic": s}) for s in state["subtopics"]]


def research_subtopic(state: SubtopicState) -> dict:
    resp = llm.invoke(f"Two key facts about: {state['subtopic']}")
    return {"findings": [f"[{state['subtopic']}] {resp.content}"]}


def write_answer(state: State) -> dict:
    notes = "\n\n".join(state["findings"])
    resp = llm.invoke(f"Answer using these notes:\n{notes}\n\nQuestion: {state['question']}")
    return {"answer": resp.content}


builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("quick_answer", quick_answer)
builder.add_node("fan_out", fan_out)
builder.add_node("search_background", search_background)
builder.add_node("search_counterpoints", search_counterpoints)
builder.add_node("research_subtopic", research_subtopic)
builder.add_node("write_answer", write_answer)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route)                     # conditional
builder.add_edge("fan_out", "search_background")                     # fixed parallel
builder.add_edge("fan_out", "search_counterpoints")                  # fixed parallel
builder.add_conditional_edges("fan_out", dispatch_subtopics, ["research_subtopic"])  # Send
builder.add_edge(
    ["search_background", "search_counterpoints", "research_subtopic"],
    "write_answer",                                                  # join all branches
)
builder.add_edge("quick_answer", END)
builder.add_edge("write_answer", END)

graph = builder.compile()
result = graph.invoke({"question": "How do CRDTs enable offline-first apps?"},
                      config={"recursion_limit": 50})
print(result["answer"])
```

All three fan-out mechanisms coexist: the two fixed branches and every `Send` branch run in the *same* super-step, their `findings` merge through `operator.add`, and the list-source edge holds `write_answer` until every branch is done.

## Key takeaways

- `add_node` registers functions whose signature can pull in `state`, `config: RunnableConfig`, and injected `runtime: Runtime[Ctx]`; `START`/`END` bound the flow; `add_edge` wires fixed transitions and list-sources create joins.
- `add_conditional_edges` routes via pure functions of state; use path maps or `Literal` annotations so the graph stays visualizable.
- `Command(goto=..., update=...)` merges "update state" and "choose next" inside a node; `Command(graph=Command.PARENT)` powers multi-agent handoffs ([08](08-multi-agent-systems.md)).
- `Send` gives dynamic map-reduce: N parallel copies of a node, each with private per-branch state, merged back through reducers.
- Every super-step counts toward `recursion_limit` (default 25); runaway loops raise `GraphRecursionError`.
- `compile()` attaches checkpointer, store, breakpoints, name, and cache; compiled graphs support `invoke`/`ainvoke`/`stream`/`astream`/`batch`.
- Prefer v1.x typed context (`context_schema` + `Runtime`, `get_runtime`) over stuffing dependencies into `config["configurable"]`; visualize everything with `graph.get_graph().draw_mermaid()`.

## Next

Continue to [04 — Streaming](04-streaming.md) to surface tokens, updates, and custom events while the graph runs.
