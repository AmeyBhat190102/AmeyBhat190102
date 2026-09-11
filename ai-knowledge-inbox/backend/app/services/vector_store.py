"""Brute-force hybrid search over the SQLite-backed chunk index.

Every ready chunk is loaded into one numpy matrix and scored with a single
matrix-vector product. At this scale that is the right call: exact recall,
no index to build, tune or corrupt, and nothing to run besides SQLite.

A 10k-chunk index at 1536 dimensions is ~60 MB of float32 and scores in
single-digit milliseconds. Past roughly 100k chunks the linear scan and the
memory both stop being reasonable; see the scaling notes in the README for
what replaces this (pgvector/Qdrant with an HNSW index).

The snapshot is cached in-process and invalidated on every write, so repeated
questions do not re-read the table.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from app.db import Database
from app.logging_config import get_logger
from app.models import ScoredChunk
from app.repositories import chunks as chunk_repo
from app.services.lexical import BM25Index, saturate

logger = get_logger(__name__)


class _IndexSnapshot:
    """Immutable view of the corpus: metadata rows, vectors, BM25 index."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.bm25 = BM25Index([row["text"] for row in rows])
        if rows:
            vectors = np.vstack([chunk_repo.decode_vector(row["embedding"]) for row in rows]).astype(np.float32)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            # Pre-normalize once so search is a plain dot product.
            self.matrix = vectors / np.where(norms == 0, 1.0, norms)
        else:
            self.matrix = np.zeros((0, 1), dtype=np.float32)

    def __len__(self) -> int:
        return len(self.rows)


class VectorStore:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._lock = threading.Lock()
        self._snapshot: _IndexSnapshot | None = None
        self._generation = 0
        self._snapshot_generation = -1

    def invalidate(self) -> None:
        """Called after any write that changes the chunk table."""
        with self._lock:
            self._generation += 1

    def _snapshot_now(self) -> _IndexSnapshot:
        with self._lock:
            if self._snapshot is not None and self._snapshot_generation == self._generation:
                return self._snapshot
            generation = self._generation

        started = time.perf_counter()
        rows = chunk_repo.load_searchable(self._db)
        snapshot = _IndexSnapshot(rows)

        with self._lock:
            self._snapshot = snapshot
            self._snapshot_generation = generation
        logger.info(
            "search index rebuilt",
            extra={"chunks": len(rows), "build_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        return snapshot

    @property
    def size(self) -> int:
        return len(self._snapshot_now())

    def search(
        self,
        *,
        query_vector: list[float],
        query_text: str,
        limit: int,
        item_ids: list[str] | None = None,
        dense_weight: float = 0.7,
    ) -> tuple[list[ScoredChunk], int]:
        """Return the `limit` best chunks and how many chunks were searched."""
        snapshot = self._snapshot_now()
        if not snapshot.rows:
            return [], 0

        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape[0] != snapshot.matrix.shape[1]:
            # Happens when the embedding provider changed after ingestion;
            # the old vectors are meaningless against the new query vector.
            logger.error(
                "embedding dimension mismatch between query and index",
                extra={"query_dim": int(vector.shape[0]), "index_dim": int(snapshot.matrix.shape[1])},
            )
            raise ValueError(
                "stored embeddings have a different dimension than the current provider; "
                "re-ingest your items after changing the embedding model"
            )

        norm = float(np.linalg.norm(vector))
        if norm:
            vector = vector / norm

        dense = np.clip(snapshot.matrix @ vector, 0.0, 1.0)
        lexical = saturate(snapshot.bm25.scores(query_text))
        combined = dense_weight * dense + (1.0 - dense_weight) * lexical

        if item_ids:
            wanted = set(item_ids)
            mask = np.array([row["item_id"] in wanted for row in snapshot.rows], dtype=bool)
            combined = np.where(mask, combined, -1.0)
            searched = int(mask.sum())
        else:
            searched = len(snapshot.rows)

        take = min(limit, combined.shape[0])
        top_indices = np.argpartition(-combined, take - 1)[:take] if take > 1 else np.array([int(np.argmax(combined))])
        ranked = sorted(top_indices, key=lambda index: float(combined[index]), reverse=True)

        hits = [
            ScoredChunk(
                chunk_id=snapshot.rows[index]["id"],
                item_id=snapshot.rows[index]["item_id"],
                item_title=snapshot.rows[index]["item_title"],
                item_source_type=snapshot.rows[index]["item_source_type"],
                item_source_url=snapshot.rows[index]["item_source_url"],
                ordinal=snapshot.rows[index]["ordinal"],
                text=snapshot.rows[index]["text"],
                dense_score=round(float(dense[index]), 4),
                lexical_score=round(float(lexical[index]), 4),
                score=round(float(combined[index]), 4),
            )
            for index in ranked
            if combined[index] >= 0.0
        ]
        return hits, searched


_store: VectorStore | None = None
_store_lock = threading.Lock()


def get_vector_store(db: Database) -> VectorStore:
    global _store
    with _store_lock:
        if _store is None or _store._db is not db:
            _store = VectorStore(db)
        return _store


def reset_vector_store() -> None:
    global _store
    with _store_lock:
        _store = None
