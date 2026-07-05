# 6. Human-in-the-loop

Autonomous agents make mistakes, and some mistakes — sending the wrong email, deleting the wrong table, refunding the wrong customer — are expensive to make and cheap to prevent. Human-in-the-loop (HITL) inserts a person at exactly the moments that matter: approving an action, editing a draft, correcting state, or supplying information the agent lacks. LangGraph's design makes this natural: because every super-step is checkpointed to a thread (see [Persistence](05-persistence-and-memory.md)), a graph can pause **indefinitely** — seconds or weeks — and resume exactly where it stopped, on a different process or machine.

## Dynamic interrupts: `interrupt()`

Call `interrupt(payload)` anywhere inside a node to pause the graph and surface the payload to the caller:

```python
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt


class State(TypedDict):
    draft: str
    approved: bool


def human_review(state: State):
    decision = interrupt({                # ── graph pauses here
        "question": "Approve this draft?",
        "draft": state["draft"],
    })
    return {"approved": decision}         # runs only after resume

builder = StateGraph(State)
builder.add_node("human_review", human_review)
builder.add_edge(START, "human_review")
builder.add_edge("human_review", END)

graph = builder.compile(checkpointer=InMemorySaver())   # checkpointer REQUIRED
config = {"configurable": {"thread_id": "review-1"}}

result = graph.invoke({"draft": "Dear customer, ...", "approved": False}, config)
print(result["__interrupt__"])
# [Interrupt(value={'question': 'Approve this draft?', 'draft': '...'},
#            id='ab1c2d...')]
```

Requirements and mechanics:

- **A checkpointer and a `thread_id` are mandatory.** The pause is persisted as a checkpoint; without them, `interrupt` raises.
- The payload can be any JSON-serializable value — send everything the human needs to decide.
- The interrupt surfaces under the `__interrupt__` key: in `invoke` results and in the stream (as an `updates` chunk). Each `Interrupt` has a `.value` (your payload) and an `.id`.
- The graph run *ends* at the pause; your process can exit. The thread holds the paused state.

## Resuming with `Command(resume=...)`

Resume by invoking the graph on the **same thread** with a `Command`:

```python
result = graph.invoke(Command(resume=True), config)
print(result)   # {'draft': 'Dear customer, ...', 'approved': True}
```

The resume value becomes the **return value of the `interrupt()` call** inside the node.

### The node re-runs from its start

This is the single most important thing to understand about `interrupt`: on resume, execution does **not** continue from the `interrupt()` line. The node function is re-executed **from its beginning**, and the `interrupt()` call now returns the resume value instead of pausing.

```python
def human_review(state: State):
    send_notification()            # BAD: runs on the first pass AND again on resume
    decision = interrupt({...})
    charge_customer()              # GOOD position: runs only after resume
    return {"approved": decision}
```

Rules of thumb:

- Put side effects **after** the `interrupt()` call, or make code before it **idempotent**.
- Expensive-but-pure work before the interrupt is merely wasteful; non-idempotent side effects before it are bugs.
- If pre-interrupt work is expensive, split it into its own node — completed nodes are checkpointed and not re-run; only the interrupted node restarts.

### Multiple parallel interrupts

If several nodes interrupt in the same super-step (parallel branches), `__interrupt__` contains several `Interrupt` objects. Resume them all at once by mapping ids to values:

```python
state = graph.get_state(config)
interrupts = state.tasks  # or result["__interrupt__"]

resume_map = {
    intr.id: f"human answer for {intr.value}"
    for task in state.tasks for intr in task.interrupts
}
graph.invoke(Command(resume=resume_map), config)
```

A bare `Command(resume=value)` answers a single pending interrupt; use the dict form whenever more than one is pending.

## Static interrupts: `interrupt_before` / `interrupt_after`

You can also pause at node boundaries without touching node code, at compile time or run time:

```python
graph = builder.compile(
    checkpointer=InMemorySaver(),
    interrupt_before=["tools"],       # pause before these nodes run
    interrupt_after=["plan"],         # pause after these nodes finish
)

# or per-run:
graph.invoke(inputs, config, interrupt_before=["tools"])
```

Resume with `invoke(None, config)` (no `Command` needed — nothing is waiting for a value). Static interrupts are **mostly a debugging tool** — stepping through a graph node by node. For production approval flows prefer `interrupt()`: it carries a payload, accepts a resume value, and marks the pause point explicitly in your business logic.

## Pattern (a): approve or reject an action

Route based on the human's answer using `Command(goto=...)`:

```python
from typing import Literal

from langgraph.types import Command, interrupt


def approval_gate(state: State) -> Command[Literal["execute_action", "revise"]]:
    decision = interrupt({
        "question": "Approve this action?",
        "action": state["planned_action"],
    })
    if decision == "approve":
        return Command(goto="execute_action")
    return Command(goto="revise", update={"feedback": decision})
```

The caller resumes with `Command(resume="approve")` or `Command(resume="rewrite it more politely")` — a rejection can double as revision guidance.

## Pattern (b): review and edit state

Let the human correct the agent's work before it propagates:

```python
def review_summary(state: State):
    edited = interrupt({
        "task": "Edit this summary if needed",
        "summary": state["summary"],
    })
    return {"summary": edited}
```

Resume with `Command(resume="the corrected summary text")`. Because the node's return value goes through the normal reducers, this is indistinguishable from the node having produced the edited text itself. (For editing *arbitrary* state outside a planned pause, use `graph.update_state` — see [Persistence](05-persistence-and-memory.md).)

## Pattern (c): review tool calls before execution

The highest-value HITL pattern for agents: intercept tool calls between the LLM that proposes them and the `ToolNode` that executes them.

```python
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from langchain_core.messages import AIMessage

llm = ChatAnthropic(model="claude-opus-4-8").bind_tools([send_email])


def agent(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}


def review_tool_calls(state: MessagesState) -> Command:
    last: AIMessage = state["messages"][-1]
    if not last.tool_calls:
        return Command(goto=END)

    decision = interrupt({
        "question": "Approve these tool calls?",
        "tool_calls": last.tool_calls,
    })
    if decision["action"] == "approve":
        return Command(goto="tools")
    if decision["action"] == "edit":
        # replace the AI message's tool calls with human-edited arguments
        edited = AIMessage(content=last.content, tool_calls=decision["tool_calls"],
                           id=last.id)   # same id => replaces via add_messages
        return Command(goto="tools", update={"messages": [edited]})
    # reject: tell the model why, let it try again
    return Command(goto="agent", update={"messages": [{
        "role": "tool", "tool_call_id": last.tool_calls[0]["id"],
        "content": f"Rejected by reviewer: {decision['reason']}",
    }]})


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("review_tool_calls", review_tool_calls)
builder.add_node("tools", ToolNode([send_email]))
builder.add_edge(START, "agent")
builder.add_edge("agent", "review_tool_calls")
builder.add_edge("tools", "agent")
graph = builder.compile(checkpointer=InMemorySaver())
```

Note the reject branch answers the pending tool call with a tool message — required to keep the message history valid for the model. Prebuilt agents offer the same idea as middleware (`HumanInTheLoopMiddleware` in `create_agent`), configurable per tool with allowed decisions (`approve` / `edit` / `reject`).

## Pattern (d): validate human input in a loop

Re-interrupt until the input passes validation — each loop iteration is a fresh interrupt:

```python
def ask_age(state: State):
    prompt = "What is your age?"
    while True:
        answer = interrupt(prompt)
        try:
            age = int(answer)
            if age > 0:
                return {"age": age}
        except (TypeError, ValueError):
            pass
        prompt = f"'{answer}' is not a valid age. Please enter a positive integer."
```

This is safe because the loop is deterministic: on each resume the node re-runs from the top, replays previously-answered `interrupt` calls from the checkpoint's resume log, and pauses at the first unanswered one.

## Interaction with streaming

An interrupt appears in the stream as a `__interrupt__` chunk (in `updates` mode), then the stream ends:

```python
for chunk in graph.stream(inputs, config, stream_mode="updates"):
    if "__interrupt__" in chunk:
        render_approval_ui(chunk["__interrupt__"][0].value)
    else:
        ...

# later, after the human responds:
for chunk in graph.stream(Command(resume=answer), config, stream_mode="updates"):
    ...
```

See [Streaming](04-streaming.md) for wiring this into an SSE endpoint: emit an `interrupt` event, keep the `thread_id` client-side, and POST the answer to a resume endpoint.

## Interaction with subgraphs

Interrupts **bubble up**: an `interrupt()` deep inside a subgraph pauses the whole parent run, and the `Interrupt` surfaces in the parent's `__interrupt__`. You resume with `Command(resume=...)` against the **parent graph's config** — you never address the subgraph directly. LangGraph routes the resume value down to the paused subgraph node. The re-execution rule compounds: the subgraph-calling node in the parent re-runs, which re-invokes the subgraph, which replays up to the paused node — another reason to keep side effects out of the path before an interrupt.

## The Agent Inbox pattern

Once interrupts are durable data on threads, HITL generalizes beyond "one user watching one stream": scan all threads for paused runs and present them as a work queue. `graph.get_state(config)` exposes pending interrupts under `snapshot.tasks[i].interrupts`; snapshot with `snapshot.next` non-empty means "awaiting action". A reviewer app lists these items, renders each payload (question, draft, tool calls), and resumes the corresponding thread with the reviewer's decision. This is exactly what the LangGraph Platform's Agent Inbox does — standardized interrupt payloads (action request + config of allowed responses: accept / edit / respond / ignore) rendered in a shared inbox UI. Self-hosted apps can implement the same contract with a table of `(thread_id, interrupt payload, status)`.

## Pitfalls

- **Interrupts are not exceptions.** `interrupt()` raises a special internal control-flow signal (`GraphInterrupt`). A bare `except Exception:` in your node (or in a library you call) can swallow it and break pausing — never wrap `interrupt()` in a broad try/except, or re-raise if you must.
- **No return value until resume.** The node produces *no* state update on the pass where it pauses. Anything computed before the interrupt is discarded and recomputed on resume; persist-worthy pre-work belongs in an earlier node.
- **Multiple interrupts in one node: matched by order.** Within a single node, resume values are replayed against `interrupt()` calls **by index in execution order**, not by payload. Keep the number and order of interrupt calls stable across re-executions — never call `interrupt()` conditionally on something that can change between the pause and the resume, and avoid multiple interrupts in one node unless the sequence is strictly deterministic (the validation loop above is fine; branching interrupt patterns are not).
- **Resuming restarts the node.** Repeated for emphasis, since it is the top source of double-sent emails: side effects go after the interrupt or must be idempotent.
- **Static interrupts don't consume `Command(resume=...)`** — they resume with `invoke(None, config)`. Mixing up the two resume styles is a common source of "my resume value disappeared" confusion.
- **A new `invoke(inputs, ...)` on a paused thread** does not resume the interrupt — passing fresh input starts a new run from the paused state. Resume with `Command(resume=...)` (dynamic) or `None` (static).

## Key takeaways

- `interrupt(payload)` pauses a graph mid-node; it requires a checkpointer and a `thread_id`, and surfaces under `__interrupt__` with an `id`.
- Resume with `Command(resume=value)` on the same thread; the value becomes `interrupt()`'s return value.
- The interrupted node re-runs from its start on resume — keep side effects after the interrupt or idempotent.
- Resume multiple pending interrupts with `Command(resume={interrupt_id: value})`.
- `interrupt_before` / `interrupt_after` are static breakpoints, resumed with `invoke(None, config)` — best for debugging.
- Core patterns: approve/reject with `Command(goto=...)`, review-and-edit state, tool-call review before `ToolNode`, and validation loops via repeated interrupts.
- Interrupts appear as `__interrupt__` chunks in streams and bubble up from subgraphs; resume always targets the parent config.
- Durable interrupts on threads enable inbox-style review queues (the Agent Inbox pattern).
- Don't swallow the interrupt signal with broad excepts, and keep interrupt call order deterministic within a node.

## Next

Continue to [7. Tools and agents](07-tools-and-agents.md).
