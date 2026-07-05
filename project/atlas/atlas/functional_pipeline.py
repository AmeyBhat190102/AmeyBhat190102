"""The same platform, Functional-API style: a knowledge-base digest pipeline.

Demonstrates `@entrypoint` / `@task`:
- tasks run in parallel by launching several and gathering their futures
- completed tasks are checkpointed — on resume after the review interrupt,
  they return cached results instead of re-running (why side effects live
  inside tasks, not in the entrypoint body)
- `entrypoint.final` separates the returned value from what is saved as the
  `previous` value for the next invocation on the same thread

Run:  python -m atlas.functional_pipeline   (requires ANTHROPIC_API_KEY)
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, RetryPolicy, interrupt

from atlas import data
from atlas.config import get_model

model = get_model(max_tokens=1024)


@task(retry_policy=RetryPolicy(max_attempts=3))
def fetch_docs(tag: str) -> list[dict]:
    """Deterministic I/O belongs in a task: replayed from cache on resume."""
    return [d for d in data.KNOWLEDGE_BASE if tag in d["tags"]] or data.KNOWLEDGE_BASE[:2]


@task
def summarize_doc(doc: dict) -> str:
    response = model.invoke(
        [
            SystemMessage(content="Summarize this support article in one sentence."),
            HumanMessage(content=f"{doc['title']}\n\n{doc['body']}"),
        ]
    )
    return f"- {doc['title']}: {response.text if isinstance(response.text, str) else response.text()}"


@entrypoint(checkpointer=InMemorySaver())
def build_digest(tag: str, *, previous: str | None = None) -> entrypoint.final[str, str]:
    docs = fetch_docs(tag).result()

    # Fan out: launch all summaries at once, then gather (parallel tasks).
    futures = [summarize_doc(doc) for doc in docs]
    summaries = [f.result() for f in futures]

    draft = f"KB digest for tag '{tag}':\n" + "\n".join(summaries)
    if previous:
        draft += "\n\n(previous digest existed; this one replaces it)"

    # Human review before publishing — pauses exactly like in the Graph API.
    verdict = interrupt({"kind": "digest_review", "draft": draft})
    published = draft if verdict.get("approved") else draft + "\n[UNPUBLISHED DRAFT]"

    # value → returned to the caller; save → next run's `previous`.
    return entrypoint.final(value=published, save=published)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "digest-demo"}}

    print("Running digest pipeline (pauses for review)...")
    for mode, chunk in build_digest.stream("nimbus", config, stream_mode=["updates", "custom"]):
        print(mode, "→", chunk)

    print("\nResuming with approval...")
    result = build_digest.invoke(Command(resume={"approved": True}), config)
    print("\n" + result)
