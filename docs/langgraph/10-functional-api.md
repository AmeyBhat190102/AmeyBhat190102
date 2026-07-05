# 10. The Functional API

LangGraph's Functional API lets you build durable, resumable workflows out of ordinary Python functions instead of declaring nodes and edges. You write one `@entrypoint` function that orchestrates work with normal control flow — `if`, `for`, `try` — and break the work into `@task` functions that run durably and in parallel. You get the same runtime features as the Graph API (checkpointing, streaming, human-in-the-loop, memory) without defining a state schema or wiring a graph. This chapter covers both decorators, how state works without a `StateGraph`, the determinism rules that make replay safe, and when to prefer each API.

## `@entrypoint`: defining a workflow

An entrypoint is the top-level unit of a functional workflow. Decorate a function with `@entrypoint`, passing a checkpointer (and optionally a store), and it becomes a runnable with the familiar `.invoke()` / `.stream()` interface:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-opus-4-8")
checkpointer = InMemorySaver()

@task
def summarize(text: str) -> str:
    response = llm.invoke(f"Summarize in two sentences:\n\n{text}")
    return response.content

@entrypoint(checkpointer=checkpointer)
def workflow(text: str) -> str:
    summary = summarize(text).result()
    return summary

config = {"configurable": {"thread_id": "thread-1"}}
result = workflow.invoke("LangGraph is a library for building agents...", config)
```

Key rules:

- An entrypoint takes **one positional input argument**. To pass multiple values, use a dict or dataclass: `workflow.invoke({"topic": "...", "style": "..."})`.
- The decorated function can also declare injectable keyword-only parameters: `previous` (last return value on this thread), `store` (a `BaseStore`), `writer` (a stream writer), and `config`. LangGraph fills these in at runtime.
- Like a compiled graph, an entrypoint supports `.invoke`, `.ainvoke`, `.stream`, and `.astream`. Checkpointing requires a `thread_id` in the config, exactly as with the Graph API.

## `@task`: durable, retryable, parallel units

A task is a discrete unit of work: an LLM call, an API request, a chunk of expensive computation. Calling a task does **not** run it inline — it schedules it and returns a future. Call `.result()` to block for the value:

```python
@task
def fetch_profile(user_id: str) -> dict:
    ...  # network call

future = fetch_profile("u-42")   # starts executing (possibly concurrently)
profile = future.result()        # blocks until done
```

Why tasks matter:

- **Durability.** Each completed task's result is persisted to the checkpointer. If the workflow is interrupted or crashes and later resumes on the same thread, finished tasks are not re-run — their saved results are returned instantly.
- **Retries.** Tasks can carry a retry policy (see below).
- **Parallelism.** Launch several tasks before calling `.result()` on any of them and they run concurrently.
- **Encapsulation of side effects.** Anything nondeterministic or effectful (API calls, randomness, writes) belongs inside a task, because the entrypoint body re-executes on resume while task results are replayed from cache.

In async code, define tasks as `async def` and `await` the future directly instead of calling `.result()`.

## State without a schema

There is no `TypedDict` state and no reducers. State is just Python variables inside your entrypoint. Two mechanisms replace what the Graph API's channels give you:

### `entrypoint.final`: decouple return value from saved value

By default, whatever the entrypoint returns is both handed to the caller and checkpointed as the thread's saved value. `entrypoint.final` lets you split the two:

```python
@entrypoint(checkpointer=checkpointer)
def counter(delta: int, *, previous: int | None = None) -> entrypoint.final[int, int]:
    current = (previous or 0)
    new_total = current + delta
    # Return the OLD total to the caller, but SAVE the new total for next time.
    return entrypoint.final(value=current, save=new_total)
```

### `previous`: short-term memory across invocations

Declare a keyword-only `previous` parameter and LangGraph injects the value saved by the last invocation on the same `thread_id` (or `None` on the first call). This is the Functional API's equivalent of thread-scoped short-term memory:

```python
@entrypoint(checkpointer=checkpointer)
def chat(user_message: str, *, previous: list | None = None) -> entrypoint.final[str, list]:
    history = (previous or []) + [{"role": "user", "content": user_message}]
    reply = llm.invoke(history)
    history.append({"role": "assistant", "content": reply.content})
    return entrypoint.final(value=reply.content, save=history)
```

For long-term, cross-thread memory, pass `store=InMemoryStore()` (or a production store) to `@entrypoint` and declare a `store` parameter — the same `BaseStore` interface used in the Graph API.

## Streaming

Streaming works identically to the Graph API. All stream modes (`"values"`, `"updates"`, `"messages"`, `"custom"`, `"debug"`) apply; `"updates"` emits one update per completed task or entrypoint:

```python
from langgraph.config import get_stream_writer

@task
def research(topic: str) -> str:
    writer = get_stream_writer()
    writer({"status": f"researching {topic}"})       # surfaces under stream_mode="custom"
    return llm.invoke(f"Research notes on {topic}").content

@entrypoint(checkpointer=checkpointer)
def pipeline(topic: str) -> str:
    return research(topic).result()

for mode, chunk in pipeline.stream("solar sails", config, stream_mode=["updates", "custom"]):
    print(mode, chunk)
```

Token-by-token LLM streaming (`stream_mode="messages"`) also works out of the box for LLM calls made inside tasks and entrypoints.

## Human-in-the-loop with `interrupt()`

`interrupt()` works inside entrypoints exactly as it does inside graph nodes: it pauses the workflow, checkpoints everything completed so far, and surfaces a payload to the caller. Resume with `Command(resume=...)`:

```python
from langgraph.types import Command, interrupt

@entrypoint(checkpointer=checkpointer)
def approval_flow(request: str) -> str:
    plan = draft_plan(request).result()          # a @task
    decision = interrupt({"plan": plan, "question": "Approve this plan?"})
    if decision == "approve":
        return execute_plan(plan).result()       # a @task
    return "Plan rejected."

# First call runs until the interrupt:
result = approval_flow.invoke("migrate the database", config)
print(result["__interrupt__"][0].value)          # {"plan": ..., "question": ...}

# Resume:
final = approval_flow.invoke(Command(resume="approve"), config)
```

Because `draft_plan` is a task, its result was checkpointed before the interrupt — on resume it is not re-executed.

## Determinism and replay rules

These rules are the heart of the Functional API. When a workflow resumes (after an interrupt, error, or crash), LangGraph **re-executes the entrypoint body from the top**, but every task call that already completed returns its cached result instead of running again. Execution fast-forwards to the point where it stopped. Consequences:

1. **Put side effects in tasks.** An API call written directly in the entrypoint body runs again on every resume. The same call inside a task runs once.
2. **Put nondeterminism in tasks.** `random.random()`, `time.time()`, or `uuid4()` in the entrypoint body can produce different values on replay and derail control flow. Wrap them in tasks so the original value is replayed.
3. **Keep task scheduling deterministic.** Task results are matched to calls by order, so don't make the sequence of task calls depend on values that can change between the original run and the replay.
4. Code between task calls in the entrypoint should be cheap and pure — it is the part that reruns.

```python
import random

@task
def roll_die() -> int:
    return random.randint(1, 6)      # correct: cached and replayed

@entrypoint(checkpointer=checkpointer)
def game(_: dict) -> str:
    roll = roll_die().result()
    answer = interrupt(f"You rolled {roll}. Guess higher or lower?")
    # On resume, roll_die() is NOT re-run — `roll` is the same value as before.
    return "correct!" if judge(roll, answer) else "wrong"
```

## Parallelism: launch, then gather

Fan-out/fan-in is plain Python — start all futures first, then collect:

```python
@task
def write_section(heading: str) -> str:
    return llm.invoke(f"Write a short section titled '{heading}'.").content

@entrypoint(checkpointer=checkpointer)
def write_report(headings: list[str]) -> str:
    futures = [write_section(h) for h in headings]   # all run concurrently
    sections = [f.result() for f in futures]          # gather
    return "\n\n".join(sections)
```

In async entrypoints, use `asyncio.gather(*futures)`.

## Interop with the Graph API

The two APIs compose freely because both are built on the same runtime:

```python
# Call a compiled graph from an entrypoint:
@entrypoint(checkpointer=checkpointer)
def orchestrator(query: str) -> str:
    graph_out = my_compiled_graph.invoke({"messages": [("user", query)]})
    return postprocess(graph_out).result()

# Call an entrypoint (or a task) from a graph node:
def node(state: MessagesState):
    answer = workflow.invoke(state["messages"][-1].content)
    return {"messages": [("assistant", answer)]}
```

When a graph is invoked inside an entrypoint on a checkpointed thread, it participates in the same thread's persistence, so interrupts raised inside the subgraph propagate up.

## Retry policies on tasks

Tasks accept the same `RetryPolicy` used for graph nodes (details in [Reliability](11-reliability.md)):

```python
from langgraph.types import RetryPolicy

@task(retry_policy=RetryPolicy(max_attempts=4, initial_interval=0.5, backoff_factor=2.0))
def flaky_api_call(url: str) -> dict:
    ...
```

> **Version note:** In LangGraph v0.x the parameter was `retry=`; v1.x renames it to `retry_policy=` (a single policy or a sequence of policies) for both `@task` and `add_node`.

## Worked example: essay writer with review

```python
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, RetryPolicy, interrupt

llm = ChatAnthropic(model="claude-opus-4-8")
checkpointer = InMemorySaver()

@task(retry_policy=RetryPolicy(max_attempts=3))
def write_essay(topic: str) -> str:
    return llm.invoke(f"Write a five-paragraph essay about {topic}.").content

@task
def revise_essay(essay: str, feedback: str) -> str:
    return llm.invoke(
        f"Revise this essay according to the feedback.\n\nFeedback: {feedback}\n\nEssay:\n{essay}"
    ).content

@entrypoint(checkpointer=checkpointer)
def essay_workflow(topic: str) -> dict:
    essay = write_essay(topic).result()
    review = interrupt({"essay": essay, "action": "Please review. Reply 'approve' or give feedback."})
    while review != "approve":
        essay = revise_essay(essay, review).result()
        review = interrupt({"essay": essay, "action": "Review the revision."})
    return {"essay": essay, "status": "approved"}

config = {"configurable": {"thread_id": "essay-1"}}
out = essay_workflow.invoke("the history of container shipping", config)
print(out["__interrupt__"][0].value["essay"])                     # draft for review

out = essay_workflow.invoke(Command(resume="Make the tone livelier."), config)  # revision loop
final = essay_workflow.invoke(Command(resume="approve"), config)
print(final["status"])  # "approved"
```

On each resume, `write_essay` and any completed `revise_essay` calls return cached results; only the next pending step actually executes.

## Graph API vs Functional API

| Dimension | Graph API (`StateGraph`) | Functional API (`@entrypoint` / `@task`) |
|---|---|---|
| Control flow | Declared as nodes + edges | Ordinary Python (`if`/`for`/`while`) |
| State | Shared schema with reducers | Local variables; `previous` + `entrypoint.final` |
| Visualization | First-class graph diagrams (Studio, Mermaid) | No inherent structure to draw |
| Parallelism | `Send` / fan-out edges, super-steps | Launch futures, then gather |
| Checkpoint granularity | Every super-step | Task boundaries + entrypoint result |
| Human-in-the-loop | `interrupt()` in nodes | `interrupt()` in entrypoint — same semantics |
| Streaming | All modes | Same modes, same `get_stream_writer` |
| Best for | Complex topologies, multi-agent, teams who want an inspectable structure | Linear-ish or code-driven workflows, wrapping existing code with durability |

Both are thin layers over the same runtime — pick per workflow, and mix them freely in one application.

## Key takeaways

- `@entrypoint` turns a function into a durable workflow; `@task` marks units of work that return futures (`.result()` to gather) and are checkpointed individually.
- State is plain Python; `previous` injects the last saved value for the thread, and `entrypoint.final(value=..., save=...)` separates what you return from what you persist.
- Streaming and `interrupt()` work exactly as in the Graph API.
- On resume, the entrypoint body re-executes but completed tasks replay cached results — so side effects and nondeterminism must live inside tasks.
- Parallelism is just launching multiple task futures before gathering them.
- Graphs and entrypoints call each other freely; choose the API per workflow using the decision table above.

## Next

Continue to [11. Reliability](11-reliability.md) for retries, caching, durability modes, error handling, and testing strategies.
