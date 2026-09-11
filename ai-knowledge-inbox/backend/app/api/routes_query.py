"""The question-answering endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import AnswererDep, DatabaseDep, EmbeddingDep, SettingsDep, VectorStoreDep
from app.db import run_db
from app.errors import ValidationError
from app.repositories import items as item_repo
from app.schemas import Citation, ErrorResponse, QueryRequest, QueryResponse
from app.services.rag import answer_question, snippet_for

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="Ask a question over saved content",
)
async def query(
    payload: QueryRequest,
    db: DatabaseDep,
    store: VectorStoreDep,
    embedder: EmbeddingDep,
    answerer: AnswererDep,
    settings: SettingsDep,
) -> QueryResponse:
    """Retrieve the most relevant chunks and answer from them alone.

    A question with nothing relevant saved returns 200 with `grounded: false`
    and no citations. That is a valid outcome, not an error: the caller asked
    a well-formed question about content that is not in the inbox.
    """
    if payload.item_ids:
        known = await run_db(item_repo.existing_ids, db, payload.item_ids)
        missing = sorted(set(payload.item_ids) - known)
        if missing:
            raise ValidationError("some item_ids do not exist", details={"unknown_item_ids": missing})

    outcome = await answer_question(
        question=payload.question,
        store=store,
        embedder=embedder,
        answerer=answerer,
        settings=settings,
        top_k=payload.top_k,
        item_ids=payload.item_ids,
    )

    return QueryResponse(
        question=outcome.question,
        answer=outcome.answer,
        grounded=outcome.grounded,
        citations=[
            Citation(
                marker=marker,
                chunk_id=passage.chunk_id,
                item_id=passage.item_id,
                title=passage.item_title,
                source_type=passage.item_source_type,
                source_url=passage.item_source_url,
                snippet=snippet_for(passage),
                score=passage.score,
            )
            for marker, passage in enumerate(outcome.passages, start=1)
        ],
        chunks_searched=outcome.chunks_searched,
        model=outcome.model,
        provider=outcome.provider,
        latency_ms=outcome.latency_ms,
    )
