"""Ingestion pipeline: raw input to searchable chunks.

One function owns the whole path (fetch, clean, chunk, embed, persist) so the
state machine on an item has exactly one place to live:

    pending -> processing -> ready
                          -> failed (error_message explains why)
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from app.config import Settings
from app.db import Database
from app.errors import AppError, ValidationError
from app.logging_config import get_logger
from app.models import EmbeddedChunk, Item
from app.repositories import chunks as chunk_repo
from app.repositories import items as item_repo
from app.schemas import NoteIngestRequest, UrlIngestRequest
from app.services.chunking import build_chunks
from app.services.embeddings import EmbeddingProvider
from app.services.text import condense, normalize_whitespace, split_sentences
from app.services.url_fetcher import fetch_document
from app.services.vector_store import VectorStore

logger = get_logger(__name__)

DEFAULT_NOTE_TITLE = "Untitled note"
TITLE_CHARS = 80


def derive_note_title(content: str) -> str:
    """Title a note from its own opening.

    A short first line is almost always a heading the user wrote. A long one
    is the start of a paragraph, and its first sentence reads far better in a
    list than 80 characters cut mid-word.
    """
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if not first_line:
        return DEFAULT_NOTE_TITLE
    if len(first_line) <= TITLE_CHARS:
        return first_line

    first_sentence = next(iter(split_sentences(first_line)), first_line)
    return first_sentence if len(first_sentence) <= TITLE_CHARS else condense(first_sentence, TITLE_CHARS)


def derive_url_title(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}" if path else parsed.netloc or url


def create_pending_item(db: Database, request: NoteIngestRequest | UrlIngestRequest, settings: Settings) -> Item:
    """Persist the item row that the caller gets back immediately."""
    if isinstance(request, NoteIngestRequest):
        content = normalize_whitespace(request.content)
        if len(content) > settings.max_note_chars:
            raise ValidationError(
                f"note exceeds the {settings.max_note_chars} character limit",
                details={"length": len(content), "limit": settings.max_note_chars},
            )
        return item_repo.create(
            db,
            source_type="note",
            title=request.title or derive_note_title(content),
            source_url=None,
            raw_content=content,
        )

    return item_repo.create(
        db,
        source_type="url",
        title=request.title or derive_url_title(request.url),
        source_url=request.url,
        raw_content="",
    )


async def process_item(
    item_id: str,
    *,
    db: Database,
    settings: Settings,
    embedder: EmbeddingProvider,
    store: VectorStore,
) -> None:
    """Run one item through the pipeline and record the outcome on the row."""
    item = item_repo.get(db, item_id)
    if item is None:
        logger.warning("ingestion skipped, item no longer exists", extra={"item_id": item_id})
        return

    started = time.perf_counter()
    item_repo.mark_processing(db, item_id)

    try:
        title, text = await _resolve_content(item, settings)
        chunks = build_chunks(
            item_id,
            text,
            target_chars=settings.chunk_target_chars,
            overlap_chars=settings.chunk_overlap_chars,
            min_chars=settings.chunk_min_chars,
        )
        if not chunks:
            raise ValidationError("no indexable text found in this item", details={"item_id": item_id})

        vectors = await embedder.embed_documents([chunk.text for chunk in chunks])
        chunk_repo.replace_for_item(
            db,
            item_id,
            [
                EmbeddedChunk(chunk=chunk, embedding=vector, embedding_model=embedder.model)
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        item_repo.mark_ready(db, item_id, title=title, raw_content=text, chunk_count=len(chunks))
        store.invalidate()

        logger.info(
            "item ingested",
            extra={
                "item_id": item_id,
                "source_type": item.source_type,
                "chars": len(text),
                "chunks": len(chunks),
                "embedding_model": embedder.model,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
    except AppError as error:
        item_repo.mark_failed(db, item_id, error.message)
        logger.warning(
            "item ingestion failed",
            extra={"item_id": item_id, "code": error.code, "reason": error.message, **error.details},
        )
    except Exception:
        item_repo.mark_failed(db, item_id, "an unexpected error occurred while processing this item")
        logger.exception("item ingestion crashed", extra={"item_id": item_id})


async def _resolve_content(item: Item, settings: Settings) -> tuple[str, str]:
    """Return (title, text) for an item, fetching the URL if needed."""
    if item.source_type == "url" and item.source_url:
        document = await fetch_document(item.source_url, settings)
        # A user-supplied title wins over the page's own <title>.
        user_titled = item.title not in ("", derive_url_title(item.source_url))
        title = item.title if user_titled else (document.title or derive_url_title(item.source_url))
        return title, document.text
    return item.title, normalize_whitespace(item.raw_content)
