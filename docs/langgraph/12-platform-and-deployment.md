# 12. Platform and deployment

A compiled LangGraph graph is just a Python object with `invoke`/`stream` methods, so you can deploy it anywhere Python runs — but stateful, long-running agents raise questions (where do checkpoints live? who runs background jobs? what happens when a user double-sends?) that a plain web framework doesn't answer. This chapter covers the self-hosting basics first, then the LangGraph Platform: a purpose-built server, APIs, CLI, and Studio debugger — kept conceptual and brief.

## Self-hosting basics

The minimal production recipe is a FastAPI (or any ASGI) wrapper around your compiled graph:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from my_app.graph import builder  # your StateGraph builder

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string("postgresql://...") as saver:
        await saver.setup()
        app.state.graph = builder.compile(checkpointer=saver)
        yield

app = FastAPI(lifespan=lifespan)

class ChatRequest(BaseModel):
    thread_id: str
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await app.state.graph.ainvoke(
        {"messages": [("user", req.message)]}, config
    )
    return {"reply": result["messages"][-1].content}
```

Production concerns to plan for:

- **Durable checkpointer.** Use `PostgresSaver`/`AsyncPostgresSaver` (package `langgraph-checkpoint-postgres`), not `InMemorySaver`. Call `.setup()` once to create tables. The same applies to the store (`PostgresStore`) if you use long-term memory.
- **Horizontal scaling.** Graph execution is stateless between steps as long as the checkpointer is shared, so N replicas behind a load balancer work — any replica can serve any thread because state lives in Postgres. Avoid per-process state like `InMemoryCache` unless cache misses are acceptable.
- **Long runs.** HTTP requests shouldn't hold a connection open for a 10-minute agent run. Either stream (SSE/WebSocket) or move execution to a task queue (Celery, Arq, etc.): the endpoint enqueues a job that invokes the graph, and clients poll or subscribe for the result. You are rebuilding what LangGraph Server provides — which is the signal to consider it.
- **Interrupts.** Expose a resume endpoint that calls `graph.invoke(Command(resume=...), config)` for the paused thread:

```python
from langgraph.types import Command

class ResumeRequest(BaseModel):
    thread_id: str
    decision: str

@app.post("/resume")
async def resume(req: ResumeRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await app.state.graph.ainvoke(Command(resume=req.decision), config)
    return {"reply": result["messages"][-1].content}
```

- **Streaming to browsers.** Wrap `graph.astream(..., stream_mode="messages")` in a server-sent-events response so tokens reach the UI as they are generated:

```python
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    async def gen():
        async for token, _meta in app.state.graph.astream(
            {"messages": [("user", req.message)]}, config, stream_mode="messages"
        ):
            yield f"data: {token.content}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

## LangGraph Platform overview

LangGraph Platform is the managed/deployable runtime for LangGraph apps. Its core is **LangGraph Server**, an API server that wraps your graphs with production plumbing: a Postgres-backed checkpointer and store, a task queue for background runs, streaming endpoints, and the concept model below.

| Concept | What it is |
|---|---|
| **Assistant** | A named configuration of a graph (graph + config/context values). One graph can back many assistants. |
| **Thread** | A conversation/state container — the same thread concept as `thread_id`, managed via API. |
| **Run** | One invocation of an assistant on a thread (foreground/streaming or background). |
| **Cron** | A scheduled run (e.g., a daily report agent). |
| **Webhook** | A URL called when a run completes, so you don't have to poll. |

### `langgraph.json`

A config file at the project root tells the server what to serve:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./my_app/graph.py:builder"
  },
  "env": ".env"
}
```

`graphs` maps assistant graph IDs to a `path:variable` pointing at a `StateGraph`/compiled graph (or an entrypoint). Two rules worth memorizing:

- You do **not** attach a checkpointer yourself — the platform injects its own Postgres-backed persistence and store. Compile without one (or guard the `checkpointer=` argument behind an "am I running locally?" check).
- `dependencies` points at installable packages (a local `"."` with a `pyproject.toml`, or pip requirements), and `env` names a dotenv file whose values are available to your graph code.

### CLI and Studio

```bash
pip install -U "langgraph-cli[inmem]"
langgraph dev    # local dev server with hot reload, in-memory persistence
langgraph up     # run the production server locally in Docker
langgraph build  # build a Docker image for deployment
```

`langgraph dev` also opens **LangGraph Studio**, a visual debugger. What it gives you, mapped to concepts from earlier chapters:

| Studio feature | Underlying mechanism |
|---|---|
| Graph diagram with live node highlighting | The compiled graph's topology |
| Per-step state inspector | `get_state` / `get_state_history` ([05 — Persistence](05-persistence-and-memory.md)) |
| Edit state, fork a thread, re-run | Time travel + `update_state` |
| Approve/edit/resume paused runs | `interrupt()` + `Command(resume=...)` ([06 — HIL](06-human-in-the-loop.md)) |
| Prompt/config tweaking per run | Assistants and context/configurable values |

Studio is the fastest way to answer "what did the state look like when this went wrong?" during development — the same questions you would otherwise answer with `get_state_history` calls in a notebook.

### Deployment options

| Option | Where it runs | Who manages it |
|---|---|---|
| Cloud SaaS | LangChain's cloud | Fully managed |
| Hybrid | Data plane (server + data) in your cloud; control plane managed | Shared |
| Self-hosted | Entirely your infrastructure | You |

All three run the same server image and expose the same API, so clients don't change between options.

## Assistants and versioning

An assistant is a graph plus a configuration — the platform analog of `context`/`configurable` values. A single deployed graph can serve, say, a "concise support agent" and a "verbose research agent" as two assistants with different system prompts and models. Edits to an assistant create **versions**, so you can experiment with prompts and roll back without redeploying code. Clients target an assistant by ID:

```python
from langgraph_sdk import get_client

client = get_client(url="http://localhost:2024")
assistant = await client.assistants.create(
    graph_id="agent", config={"configurable": {"system_prompt": "Be concise."}}
)
thread = await client.threads.create()
async for chunk in client.runs.stream(
    thread["thread_id"], assistant["assistant_id"],
    input={"messages": [("user", "hi")]}, stream_mode="messages",
):
    print(chunk)
```

## Double-texting strategies

What happens when a user sends a second message while a run is still executing? The server supports four per-run strategies via `multitask_strategy`:

| Strategy | Behavior | Use when |
|---|---|---|
| `reject` | Refuse the new run with an error | Strict one-at-a-time flows |
| `enqueue` | Queue the new run to start after the current one finishes | Every message matters |
| `interrupt` | Stop the current run (keeping work done so far in the thread), start the new one | Chat UX: the new message supersedes |
| `rollback` | Cancel the current run and revert the thread to its state before that run, then start the new one | The interrupted run should leave no trace |

```python
await client.runs.create(
    thread_id, assistant_id,
    input={"messages": [("user", "actually, make it shorter")]},
    multitask_strategy="interrupt",
)
```

If you self-host without the platform, this is exactly the kind of edge case you must design yourself — most home-grown deployments silently behave like `enqueue` (requests serialize on the thread) or corrupt state by running two writes concurrently.

## Background runs, polling, and streaming

For long-running agents, create a run without holding a connection:

```python
run = await client.runs.create(thread_id, assistant_id, input=inputs)

# Option 1: poll
run = await client.runs.get(thread_id, run["run_id"])       # status: pending/running/success/error

# Option 2: join the stream of an in-flight run
async for chunk in client.runs.join_stream(thread_id, run["run_id"]):
    ...

# Option 3: webhook — pass webhook="https://your.app/hooks/run-done" at creation
```

Runs execute on the server's task queue with retries and heartbeats, so a worker crash re-queues the run instead of losing it.

## Cron jobs

Crons schedule runs — with or without a fixed thread:

```python
await client.crons.create(
    assistant_id,
    schedule="0 8 * * MON",     # every Monday 08:00 UTC
    input={"messages": [("user", "Compile the weekly metrics report.")]},
)
```

Delete crons you no longer need; they run (and bill) until removed.

## Auth hooks (brief)

Self-hosted and enterprise deployments can plug in custom authentication and authorization: an `@auth.authenticate` handler validates the caller (e.g., checks a JWT) and returns an identity, and `@auth.on` resource handlers filter what that identity may do per resource (threads, assistants, runs) — for example, restricting users to threads they own:

```python
from langgraph_sdk import Auth

auth = Auth()

@auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    user = await validate_jwt(headers.get("authorization"))
    return {"identity": user.id}

@auth.on.threads
async def owner_only(ctx: Auth.types.AuthContext, value: dict):
    # Stamp ownership on create; filter reads to the owner's threads.
    filters = {"owner": ctx.user.identity}
    value.setdefault("metadata", {}).update(filters)
    return filters
```

Point `langgraph.json` at it with `"auth": {"path": "./my_app/auth.py:auth"}`. The mental model: authentication decides *who you are*, authorization handlers decide *which threads/assistants/runs you can see and touch*.

## Platform vs a simple FastAPI service

| Your situation | Recommendation |
|---|---|
| Short-lived request/response graphs, no interrupts, modest scale | FastAPI wrapper + Postgres checkpointer is plenty |
| You already run Celery/queues and want full infra control | Self-host your own stack; borrow the patterns above |
| Long-running or background agent runs | Platform (built-in task queue, webhooks, join-stream) |
| Human-in-the-loop at scale (many paused threads) | Platform (threads/runs APIs, Studio for inspection) |
| Frequent prompt/config experimentation without redeploys | Platform (assistants + versioning) |
| Bursty chat traffic with users double-sending | Platform (double-texting strategies out of the box) |
| Scheduled agent jobs, org-wide agent APIs, non-Python clients | Platform (crons, standardized REST API, JS/Python SDKs) |

The honest framing: everything the platform does can be built on a plain web stack — the question is whether queues, resumability, versioning, and a debugger UI are your product or your plumbing.

## Key takeaways

- A compiled graph deploys like any Python object; the minimum production setup is an ASGI wrapper plus a Postgres checkpointer, with replicas sharing state through the database.
- LangGraph Server adds Assistants, Threads, Runs, Crons, and Webhooks on top of your graphs; `langgraph.json` declares the graphs, and `langgraph dev` / `langgraph up` run it locally.
- LangGraph Studio is a visual debugger with state inspection, time travel, and interrupt handling built on the same persistence APIs you've already learned.
- Assistants are versioned configurations of a graph — change behavior without redeploying code.
- Double-texting strategies (`reject`, `enqueue`, `interrupt`, `rollback`) define what a second concurrent message does to an in-flight run.
- Choose the platform when background runs, HIL at scale, versioning, or scheduling would otherwise become your plumbing; a FastAPI wrapper is fine for simple request/response graphs.

## Next

Finish with the [13. Glossary](13-glossary.md) — an A-Z reference for every term in this documentation set.
