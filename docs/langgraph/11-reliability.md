# 11. Reliability

LangGraph applications call flaky networks, run expensive model inference, and pause mid-execution for humans — all of which invite failure. This chapter covers the features that keep production graphs healthy: automatic retries, node caching, durability modes and crash recovery, structured error handling, timeouts and recursion limits, side-effect discipline, observability with LangSmith, and practical testing strategies.

## RetryPolicy: automatic retries

`RetryPolicy` (from `langgraph.types`) declares how a failing node or task should be retried:

```python
from langgraph.types import RetryPolicy

policy = RetryPolicy(
    max_attempts=3,        # total attempts, including the first
    initial_interval=0.5,  # seconds before the first retry
    backoff_factor=2.0,    # each wait = previous wait * factor
    jitter=True,           # add randomness to avoid thundering herds
    retry_on=ConnectionError,  # exception type(s), or a callable(exc) -> bool
)
```

By default `retry_on` skips exceptions that are almost never transient (`ValueError`, `TypeError`, most 4xx HTTP errors) and retries network-ish failures. Pass a tuple of exception types or a predicate for full control.

Apply a policy per node in the Graph API, or per task in the Functional API:

```python
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.func import task
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-opus-4-8")

def call_model(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model, retry_policy=RetryPolicy(max_attempts=3))

@task(retry_policy=RetryPolicy(max_attempts=5, retry_on=TimeoutError))
def fetch_data(url: str) -> dict:
    ...
```

> **Version note:** v0.x used `add_node(..., retry=policy)` and `@task(retry=policy)`; v1.x renames the parameter to `retry_policy` and accepts either a single `RetryPolicy` or a sequence of them (first matching policy wins).

Retries happen inside the node's super-step: state written by other nodes is untouched, and a successful retry proceeds as if nothing failed.

## CachePolicy: skip recomputing expensive nodes

Node caching returns a stored result when a node is called again with identical input — useful for expensive, deterministic, or rate-limited work:

```python
from langgraph.types import CachePolicy
from langgraph.cache.memory import InMemoryCache

def expensive_analysis(state: MessagesState):
    ...  # slow model call or computation

builder = StateGraph(MessagesState)
builder.add_node(
    "analysis",
    expensive_analysis,
    cache_policy=CachePolicy(ttl=120),  # seconds; None = never expires
)
graph = builder.compile(cache=InMemoryCache())
```

Two pieces are required: a `cache_policy` on the node **and** a `cache` backend passed to `compile()`. The cache key defaults to a hash of the node's input; supply `CachePolicy(key_func=...)` to key on a subset of state (for example, only the last message) so irrelevant state changes don't bust the cache. `InMemoryCache` is per-process; for multi-worker deployments use a shared backend such as the SQLite cache or the caching built into LangGraph Platform.

Caching is orthogonal to checkpointing: checkpoints replay results *within a thread's history*, while a cache shares results *across runs and threads* with the same input.

## Durability modes and crash recovery

With a checkpointer attached, `invoke`/`stream` accept a `durability` argument controlling when checkpoints are written:

| Mode | Behavior | Trade-off |
|---|---|---|
| `"exit"` | Checkpoint only when the run finishes | Fastest; no mid-run crash recovery |
| `"async"` (default) | Write checkpoints in the background while the next step runs | Good balance; tiny window where a crash loses the latest step |
| `"sync"` | Write and confirm each checkpoint before the next step starts | Maximum safety; highest latency |

> **Version note:** v0.x exposed this as `checkpoint_during=True/False`; v1.x replaces it with the three-valued `durability` parameter.

Recovery after a crash or interrupt uses the same two moves:

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": "job-17"}}

# 1. Paused at an interrupt() -> resume with a value:
graph.invoke(Command(resume="approved"), config)

# 2. Crashed mid-run (process died, exception escaped) -> re-invoke with None
#    on the same thread to continue from the last checkpoint:
graph.invoke(None, config)
```

Because completed super-steps (and completed tasks, in the Functional API) are checkpointed, re-invocation resumes from the last saved point rather than starting over. Use a production checkpointer (`PostgresSaver`) so checkpoints survive process death — `InMemorySaver` does not.

## Handling tool and node errors

Retries handle transient failures; for expected failures you want the graph to *route around* the problem instead of crashing.

**Catch inside the node and write error state:**

```python
from typing import TypedDict

class State(TypedDict):
    query: str
    result: str | None
    error: str | None

def risky_node(state: State):
    try:
        return {"result": call_external_service(state["query"]), "error": None}
    except ServiceError as e:
        return {"result": None, "error": str(e)}

def route_after_risky(state: State) -> str:
    return "handle_error" if state["error"] else "continue"

builder.add_conditional_edges("risky", route_after_risky,
                              {"handle_error": "fallback", "continue": "next_step"})
```

**Tool errors with `ToolNode`:** the prebuilt `ToolNode` catches tool exceptions and returns them to the model as a `ToolMessage`, letting the LLM self-correct. Tune this with `handle_tool_errors`:

```python
from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools, handle_tool_errors=True)                  # default: send error text back to the model
tool_node = ToolNode(tools, handle_tool_errors="Tool failed, try different arguments.")  # custom message
tool_node = ToolNode(tools, handle_tool_errors=False)                 # raise: let RetryPolicy or the caller deal with it
```

Pick one layer to own each error: don't both retry an exception and swallow it into a `ToolMessage`, or you'll mask real bugs.

## Timeouts and recursion limits

**Step timeout.** Bound how long any single super-step may run:

```python
graph = builder.compile()
graph.step_timeout = 60  # seconds per step; raises on breach
```

**Recursion limit.** Every invocation has a cap on super-steps (default 25). Cycling graphs — agents especially — should treat it as a safety valve against infinite loops:

```python
from langgraph.errors import GraphRecursionError

try:
    graph.invoke(inputs, {"recursion_limit": 50, **config})
except GraphRecursionError:
    ...  # give up gracefully, or report partial progress
```

To degrade gracefully *before* the exception, use the `RemainingSteps` managed value — LangGraph injects the number of steps left, so a routing function can bail out to `END` when the budget is nearly exhausted:

```python
from typing import Annotated
from langgraph.managed import RemainingSteps

class State(MessagesState):
    remaining_steps: RemainingSteps

def route(state: State):
    if state["remaining_steps"] <= 2:
        return END          # wrap up instead of crashing
    return "tools"
```

## Idempotency and side-effect placement

Resume semantics re-execute code. In the Graph API, resuming after an `interrupt()` re-runs the interrupted **node from its beginning** up to the interrupt call; in the Functional API, the **entrypoint body** re-runs while completed tasks replay cached results. Therefore:

- Put side effects (payments, emails, DB writes) *after* the `interrupt()` in a node, or in their own node/task, so they don't fire twice.
- Make unavoidable pre-interrupt effects idempotent (e.g., idempotency keys on API calls).
- Don't branch on nondeterministic values (time, randomness) computed in re-executed code — wrap them in a task or a dedicated node so the value is checkpointed.

```python
def approve_and_pay(state: State):
    decision = interrupt({"amount": state["amount"]})   # node re-runs up to here on resume
    if decision == "approve":
        charge_customer(state["amount"])                # after interrupt: runs exactly once
    return {"status": decision}
```

## Observability with LangSmith

LangSmith traces every super-step, node execution, LLM call, and tool call with zero code changes — set environment variables and run:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<your-key>
export LANGSMITH_PROJECT=my-agent   # optional project name
```

Traces show the full tree (graph → node → LLM/tool), latency, token usage, and errors, which makes "why did the agent loop?" a lookup instead of an archaeology dig. LangSmith also supports datasets and evaluators for scoring agent behavior over example suites — pair trajectory-level evaluations (did it call the right tools in the right order?) with final-output evaluations. That workflow is beyond this chapter's scope; the key point is that tracing is one env var away and costs nothing to leave on in staging.

## Testing strategies

Graphs decompose into pieces that are each easy to test.

**1. Unit-test nodes as plain functions.** Nodes take state and return updates — no graph needed:

```python
def test_summarize_node():
    state = {"messages": [HumanMessage("hello " * 300)]}
    update = summarize_node(state)
    assert "summary" in update
```

**2. Test routing functions directly.** They're pure functions from state to a branch name:

```python
def test_routes_to_tools_when_tool_calls_present():
    state = {"messages": [AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "1", "type": "tool_call"}])]}
    assert route_model_output(state) == "tools"
```

**3. Integration-test with a fake chat model.** `GenericFakeChatModel` replays scripted responses (including tool calls) so tests are fast, free, and deterministic:

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

fake_llm = GenericFakeChatModel(messages=iter([
    AIMessage(content="", tool_calls=[{"name": "search", "args": {"q": "weather"}, "id": "1", "type": "tool_call"}]),
    AIMessage(content="It's sunny in SF."),
]))

graph = build_graph(llm=fake_llm).compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "test-1"}}
result = graph.invoke({"messages": [("user", "weather in SF?")]}, config)
assert "sunny" in result["messages"][-1].content
```

Inject the model as a parameter of your graph builder (as above) so production and tests share one construction path.

**4. Snapshot and assert on state.** With a checkpointer attached, inspect intermediate state via `graph.get_state(config)` and full history via `graph.get_state_history(config)` — assert on which node is `next`, on interrupt payloads, or on the exact sequence of super-steps. For interrupt flows, assert the first invoke returns `__interrupt__`, then resume with `Command(resume=...)` and assert the final state.

## Key takeaways

- `RetryPolicy(max_attempts, initial_interval, backoff_factor, jitter, retry_on)` attaches to nodes (`add_node(..., retry_policy=...)`) and tasks; retries stay inside the failing step.
- `CachePolicy(ttl=...)` on a node plus `compile(cache=InMemoryCache())` skips recomputing nodes on identical input; caching is cross-thread, checkpoints are per-thread.
- Durability modes trade latency for crash safety (`"exit"` < `"async"` < `"sync"`); recover by resuming with `Command(resume=...)` or re-invoking with `None` on the same thread.
- Handle expected failures structurally: try/except in nodes writing error state, `handle_tool_errors` on `ToolNode`, and error-routing edges.
- `step_timeout` bounds a step; `recursion_limit` plus `RemainingSteps` prevents and gracefully handles runaway loops.
- Side effects belong after interrupts or inside tasks; re-executed code must be cheap, pure, and deterministic.
- Turn on LangSmith tracing with env vars; test nodes and routers as plain functions and integration-test with `GenericFakeChatModel` + `InMemorySaver`.

## Next

Continue to [12. Platform and deployment](12-platform-and-deployment.md) for running LangGraph apps in production.
