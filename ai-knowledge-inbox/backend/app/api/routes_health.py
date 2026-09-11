"""Liveness and configuration introspection."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import AnswererDep, DatabaseDep, EmbeddingDep, QueueDep
from app.db import run_db
from app.repositories import chunks as chunk_repo
from app.repositories import items as item_repo
from app.schemas import HealthResponse, ProviderInfo

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse, summary="Service state and active providers")
async def health(
    db: DatabaseDep,
    embedder: EmbeddingDep,
    answerer: AnswererDep,
    queue: QueueDep,
) -> HealthResponse:
    """Reports which providers are live, so a surprising answer can be traced
    to a local fallback rather than assumed to be a model failure."""
    item_count = await run_db(item_repo.count, db)
    chunk_count = await run_db(chunk_repo.count, db)
    return HealthResponse(
        status="ok",
        items=item_count,
        chunks=chunk_count,
        pending_jobs=queue.pending,
        providers=ProviderInfo(
            embeddings=embedder.name,
            embedding_model=embedder.model,
            llm=answerer.name,
            llm_model=answerer.model,
        ),
    )
