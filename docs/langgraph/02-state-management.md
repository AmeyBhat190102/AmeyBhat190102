# 2. State Management

State is the shared, typed data structure that flows through every node in a LangGraph graph — it is how nodes communicate, what checkpointers save, and what you get back from `invoke()`. This file covers how to define state schemas, how updates actually get applied (reducers), the special `add_messages` reducer and `MessagesState`, multiple schemas for input/output/private data, how state relates to config and runtime context, and the pitfalls that bite almost everyone once.

## Defining a state schema

The schema declares every key your graph reads or writes. Three options, in order of how often you'll use them:

### TypedDict (the default choice)

```python
from typing import TypedDict


class State(TypedDict):
    question: str
    documents: list[str]
    answer: str
```

Fast (plain dicts at runtime), zero dependencies, great IDE support. No runtime validation — a node can return `{"answer": 42}` and nothing complains until something downstream breaks. Use `typing.NotRequired`/`total=False` for optional keys.

### Pydantic BaseModel (when you want runtime validation)

```python
from pydantic import BaseModel, Field


class State(BaseModel):
    question: str
    documents: list[str] = Field(default_factory=list)
    answer: str = ""
```

LangGraph validates **node inputs** against the model at runtime and applies defaults. There is real overhead per node transition, and two subtleties: validation applies to inputs (bad *outputs* surface when the next node receives them), and nodes still **return plain dicts** as updates, not `State` instances.

### Dataclasses (a middle ground)

```python
from dataclasses import dataclass, field


@dataclass
class State:
    question: str
    documents: list[str] = field(default_factory=list)
    answer: str = ""
```

Defaults without Pydantic's overhead; no runtime validation. Inside nodes you access fields with attribute syntax (`state.question`) instead of subscripting.

| | TypedDict | Pydantic BaseModel | dataclass |
|---|---|---|---|
| Runtime validation | No | Yes (inputs) | No |
| Default values | No (use `total=False`) | Yes | Yes |
| Performance | Best | Slowest | Good |
| Access in nodes | `state["key"]` | `state.key` | `state.key` |
| Recommendation | Default choice | Untrusted/complex inputs | Want defaults, not validation |

Whichever you pick, **nodes always return a plain `dict` of updates.**

## How updates work: partial updates, not whole state

A node never returns (or mutates) the full state. It returns a dict containing **only the keys it wants to change**:

```python
def retrieve(state: State) -> dict:
    docs = search(state["question"])
    return {"documents": docs}      # 'question' and 'answer' untouched
```

The runtime takes that update and applies it to the channel for each key. *How* it applies it is decided per key by a **reducer**.

## Reducers

A reducer is a function `(current_value, update) -> new_value` attached to a state key. Reducers are what make concurrent updates within a super-step deterministic and what let you express "append" instead of "replace".

### Default: overwrite

Keys without a reducer are simply overwritten:

```python
class State(TypedDict):
    answer: str        # node returns {"answer": "x"} → answer becomes "x"
```

This is fine for single-writer keys, and a bug factory for lists you meant to accumulate — and if **two parallel nodes** write an overwrite-key in the same super-step, LangGraph raises an `InvalidUpdateError` because there is no deterministic way to pick a winner.

### `Annotated[..., reducer]` — built-in accumulation

Attach a reducer with `typing.Annotated`. The most common is `operator.add` (list concatenation):

```python
import operator
from typing import Annotated, TypedDict


class State(TypedDict):
    question: str                                  # overwrite
    documents: Annotated[list[str], operator.add]  # append


def node_a(state: State) -> dict:
    return {"documents": ["doc-a"]}


def node_b(state: State) -> dict:
    return {"documents": ["doc-b"]}
```

If `node_a` and `node_b` run in parallel in the same super-step, `documents` ends up containing both `"doc-a"` and `"doc-b"` — each update is *added to*, not *swapped over*, the current value. This is the mechanism behind safe parallel fan-out (see [Graph API](03-graph-api.md)).

### Custom reducer functions

Any `(left, right) -> merged` callable works:

```python
from typing import Annotated, TypedDict


def merge_unique(existing: list[str], new: list[str]) -> list[str]:
    """Append, dropping duplicates, preserving order."""
    seen = set(existing)
    return existing + [x for x in new if x not in seen]


def take_max(current: float, update: float) -> float:
    return max(current, update)


class State(TypedDict):
    sources: Annotated[list[str], merge_unique]
    best_score: Annotated[float, take_max]
```

Keep reducers **pure and fast** — they run on every update, including during checkpoint replay, so side effects or slow work inside a reducer will haunt you.

### `add_messages` — the reducer for chat history

`add_messages` is a purpose-built reducer for lists of LangChain messages with three behaviors:

1. **Append** — new messages are added to the end of the list.
2. **Upsert by ID** — an incoming message whose `id` matches an existing one **replaces** it instead of appending. This is how streaming partials, message edits, and retries stay clean.
3. **Deletion via `RemoveMessage`** — returning `RemoveMessage(id=...)` deletes the message with that ID; `RemoveMessage(id=REMOVE_ALL_MESSAGES)` clears the history.

It also coerces convenient shorthand (like `{"role": "user", "content": "hi"}` or a bare string) into proper message objects.

```python
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import add_messages, REMOVE_ALL_MESSAGES


class State(TypedDict):
    messages: Annotated[list, add_messages]


def trim_history(state: State) -> dict:
    """Keep only the last 4 messages by deleting the rest."""
    to_delete = state["messages"][:-4]
    return {"messages": [RemoveMessage(id=m.id) for m in to_delete]}
```

## `MessagesState`: the prebuilt, and extending it

Because a `messages` key with `add_messages` is so common, LangGraph ships it:

```python
from langgraph.graph import MessagesState   # == TypedDict with messages: Annotated[list, add_messages]
```

Extend it by subclassing when you need extra keys:

```python
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState

llm = ChatAnthropic(model="claude-opus-4-8")


class State(MessagesState):        # inherits `messages` with add_messages
    summary: str
    user_name: str


def chatbot(state: State) -> dict:
    system = f"You are talking to {state.get('user_name', 'a user')}."
    response = llm.invoke([{"role": "system", "content": system}, *state["messages"]])
    return {"messages": [response]}     # add_messages appends it


builder = StateGraph(State)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)
graph = builder.compile()

out = graph.invoke({"messages": [{"role": "user", "content": "Hi!"}], "user_name": "Amey"})
print(out["messages"][-1].content)
```

## Multiple schemas: input, output, and private state

By default one schema serves as input, output, and internal state. You can split them.

### Input and output schemas

Constrain what callers pass in and what `invoke()` returns, while nodes work with a richer internal schema:

```python
from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class InputState(TypedDict):
    question: str


class OutputState(TypedDict):
    answer: str


class OverallState(TypedDict):      # superset used internally
    question: str
    notes: str
    answer: str


def think(state: OverallState) -> dict:
    return {"notes": f"Deconstructing: {state['question']}"}


def answer(state: OverallState) -> dict:
    return {"answer": f"Based on {state['notes']!r}: 42"}


builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_node("think", think)
builder.add_node("answer", answer)
builder.add_edge(START, "think")
builder.add_edge("think", "answer")
builder.add_edge("answer", END)
graph = builder.compile()

print(graph.invoke({"question": "meaning of life?"}))
# {'answer': "Based on 'Deconstructing: meaning of life?': 42"}  ← notes filtered out
```

> **Version note:** In LangGraph v0.x these parameters were named `input=`/`output=`; v1.x renames them to `input_schema=`/`output_schema=` (and `StateGraph(State, config_schema=...)` became `context_schema=` — see [Graph API](03-graph-api.md)).

### Private state between specific nodes

A node can declare an input schema that isn't part of the overall state at all — useful for scratch data that only one pair of nodes shares. Keys in the writing node's returned dict that belong to the private schema are routed to nodes that declare it, without polluting the graph's output:

```python
from typing import TypedDict

from langgraph.graph import StateGraph, START, END


class OverallState(TypedDict):
    question: str
    answer: str


class ScratchPad(TypedDict):        # private: never appears in graph output
    draft: str


def draft_node(state: OverallState) -> ScratchPad:
    return {"draft": f"DRAFT re {state['question']}"}


def polish_node(state: ScratchPad) -> OverallState:   # reads only the private schema
    return {"answer": state["draft"].replace("DRAFT", "Final answer")}


builder = StateGraph(OverallState)
builder.add_node("draft_node", draft_node)
builder.add_node("polish_node", polish_node)
builder.add_edge(START, "draft_node")
builder.add_edge("draft_node", "polish_node")
builder.add_edge("polish_node", END)
graph = builder.compile()

print(graph.invoke({"question": "why is the sky blue?"}))
# {'question': 'why is the sky blue?', 'answer': 'Final answer re why is the sky blue?'}
```

## State vs. config vs. runtime context vs. store

Four different homes for data — choosing the right one is half of good LangGraph design:

| | **State** | **Config (`configurable`)** | **Runtime context (`context` + `Runtime`)** | **Long-term store** |
|---|---|---|---|---|
| Holds | Data that changes during a run | Run metadata: `thread_id`, checkpoint ids | Immutable per-run dependencies: user id, db handles, model choice | Knowledge across threads/users |
| Mutable during run | Yes (via node updates) | No | No | Yes (explicit `store.put`) |
| Checkpointed | Yes | Identifies the checkpoint | No | Persisted separately |
| Typed schema | State schema | No | `context_schema` | No |
| Access in node | First positional arg | `config` second arg | `Runtime[Ctx]` injected arg | `store` injected / `runtime.store` |
| Example | `messages`, `documents` | `{"configurable": {"thread_id": "t1"}}` | `context={"user_id": "u42"}` | user preferences, learned facts |

Rule of thumb: if the graph *computes* it, it's state; if it *identifies the run*, it's config; if the run *depends on it but never changes it*, it's runtime context; if it must *outlive the thread*, it's the store. Details on context injection in [Graph API](03-graph-api.md); stores in [Persistence & memory](05-persistence-and-memory.md).

## Common pitfalls

- **Mutating state in place.** `state["documents"].append(doc)` inside a node mutates the checkpointed object, bypasses reducers, and corrupts replay/time-travel. Always build a new value and return it: `return {"documents": [doc]}` (with an additive reducer) or `return {"documents": state["documents"] + [doc]}`.
- **Forgetting a reducer and silently overwriting.** A `list` key without `operator.add`/`add_messages` is *replaced* on every update. Symptom: your chat history is always exactly one message long. Fix: `Annotated[list, add_messages]`.
- **Parallel writers on an overwrite key.** Two fan-out branches writing the same non-reduced key raise `InvalidUpdateError: Can receive only one value per step`. Fix: add a reducer that defines how to merge.
- **Unserializable objects in state.** Database connections, clients, locks, open files — checkpointers must serialize the whole state, and these will fail (or worse, "work" in `InMemorySaver` and blow up in Postgres). Keep live objects in runtime context; keep state to data.
- **Returning the whole state "to be safe".** It usually works but re-triggers reducers on keys you didn't change (duplicating list contents, for example). Return only the changed keys.
- **Confusing node input validation with output validation (Pydantic).** A node emitting a wrong-typed value won't fail at return time — the error appears when the *next* node validates its input, which makes stack traces point one node too late.

## Key takeaways

- Define state as a `TypedDict` by default; Pydantic when you need runtime validation; dataclass for defaults without validation. Nodes always return plain dicts of **partial updates**.
- Reducers decide how updates apply per key: default is overwrite; `Annotated[list, operator.add]` appends; custom reducers implement any merge; parallel writers *require* a reducer.
- `add_messages` appends, upserts by message ID, and honors `RemoveMessage` deletions — `MessagesState` gives you that key prebuilt, and you extend it by subclassing.
- Use `input_schema`/`output_schema` to narrow the graph's public interface, and private node schemas for scratch data between specific nodes.
- State ≠ config ≠ runtime context ≠ store: computed data, run identity, immutable dependencies, and cross-thread knowledge each live in a different place.
- Never mutate state in place, never checkpoint live objects, never leave accumulating keys without a reducer.

## Next

Continue to [03 — Graph API](03-graph-api.md) for the full node/edge/routing toolkit built on top of these state semantics.
