"""FastAPI dependency wiring.

Route handlers ask for what they need and get a single shared instance, which
keeps the providers and the search index out of module-level globals inside
the route modules and makes them straightforward to override in tests.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.db import Database, get_database
from app.services.answering import Answerer, get_answerer
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.jobs import IngestionQueue
from app.services.vector_store import VectorStore, get_vector_store


def settings_dependency() -> Settings:
    return get_settings()


def database_dependency() -> Database:
    return get_database()


def vector_store_dependency(db: Annotated[Database, Depends(database_dependency)]) -> VectorStore:
    return get_vector_store(db)


def embedding_dependency() -> EmbeddingProvider:
    return get_embedding_provider()


def answerer_dependency() -> Answerer:
    return get_answerer()


def queue_dependency(request: Request) -> IngestionQueue:
    return request.app.state.ingestion_queue


SettingsDep = Annotated[Settings, Depends(settings_dependency)]
DatabaseDep = Annotated[Database, Depends(database_dependency)]
VectorStoreDep = Annotated[VectorStore, Depends(vector_store_dependency)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(embedding_dependency)]
AnswererDep = Annotated[Answerer, Depends(answerer_dependency)]
QueueDep = Annotated[IngestionQueue, Depends(queue_dependency)]
