"""Query orchestration: embed, retrieve, select, answer, cite.

This is the only place that knows the shape of the whole RAG flow. Each step
it calls is independently testable, and the selection policy between
retrieval and generation is explicit rather than buried in a prompt.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from app.config import Settings
from app.logging_config import get_logger
from app.models import ScoredChunk
from app.services.answering import NO_ANSWER_TEXT, Answerer
from app.services.embeddings import EmbeddingProvider
from app.services.text import condense
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

SNIPPET_CHARS = 320
EMPTY_INBOX_TEXT = "Nothing has been saved yet, so there is nothing to search."
_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(slots=True)
class QueryOutcome:
    question: str
    answer: str
    grounded: bool
    passages: list[ScoredChunk]
    chunks_searched: int
    provider: str
    model: str
    latency_ms: int


def select_passages(
    candidates: list[ScoredChunk],
    *,
    top_k: int,
    min_score: float,
    max_per_item: int,
) -> list[ScoredChunk]:
    """Trim retrieval output down to what actually goes in the prompt.

    Two rules: drop anything below the relevance floor, and cap how many
    chunks one item may contribute. The cap matters because a long document
    can otherwise fill the whole context with near-duplicate neighbours and
    crowd out a shorter note that answers the question directly.
    """
    selected: list[ScoredChunk] = []
    per_item: dict[str, int] = {}

    for candidate in candidates:
        if candidate.score < min_score:
            continue
        used = per_item.get(candidate.item_id, 0)
        if used >= max_per_item:
            continue
        per_item[candidate.item_id] = used + 1
        selected.append(candidate)
        if len(selected) >= top_k:
            break
    return selected


def _warn_on_invalid_markers(answer: str, passage_count: int) -> None:
    referenced = {int(marker) for marker in _MARKER.findall(answer)}
    invalid = {marker for marker in referenced if marker < 1 or marker > passage_count}
    if invalid:
        logger.warning(
            "answer cited a passage that was not in context",
            extra={"invalid_markers": sorted(invalid), "passage_count": passage_count},
        )


async def answer_question(
    *,
    question: str,
    store: VectorStore,
    embedder: EmbeddingProvider,
    answerer: Answerer,
    settings: Settings,
    top_k: int | None = None,
    item_ids: list[str] | None = None,
) -> QueryOutcome:
    started = time.perf_counter()
    effective_top_k = top_k or settings.retrieval_top_k

    query_vector = await embedder.embed_query(question)
    candidates, searched = store.search(
        query_vector=query_vector,
        query_text=question,
        limit=max(settings.retrieval_candidate_k, effective_top_k),
        item_ids=item_ids,
        dense_weight=settings.retrieval_dense_weight,
    )
    passages = select_passages(
        candidates,
        top_k=effective_top_k,
        min_score=settings.retrieval_min_score,
        max_per_item=settings.max_chunks_per_item_in_context,
    )

    if not passages:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "query answered without context",
            extra={
                "chunks_searched": searched,
                "top_candidate_score": round(candidates[0].score, 4) if candidates else None,
                "min_score": settings.retrieval_min_score,
                "latency_ms": elapsed_ms,
            },
        )
        return QueryOutcome(
            question=question,
            answer=EMPTY_INBOX_TEXT if searched == 0 else NO_ANSWER_TEXT,
            grounded=False,
            passages=[],
            chunks_searched=searched,
            provider=answerer.name,
            model=answerer.model,
            latency_ms=elapsed_ms,
        )

    answer = await answerer.answer(question, passages)
    _warn_on_invalid_markers(answer, len(passages))
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "query answered",
        extra={
            "chunks_searched": searched,
            "passages_used": len(passages),
            "top_score": passages[0].score,
            "cited_items": sorted({passage.item_id for passage in passages}),
            "provider": answerer.name,
            "model": answerer.model,
            "latency_ms": elapsed_ms,
        },
    )
    return QueryOutcome(
        question=question,
        answer=answer,
        grounded=True,
        passages=passages,
        chunks_searched=searched,
        provider=answerer.name,
        model=answerer.model,
        latency_ms=elapsed_ms,
    )


def snippet_for(passage: ScoredChunk) -> str:
    return condense(passage.text, SNIPPET_CHARS)
