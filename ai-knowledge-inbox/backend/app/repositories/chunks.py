"""Persistence for chunks and their embedding vectors.

Vectors are stored as float32 BLOBs rather than JSON: 4 bytes per dimension
instead of ~12-20, and they load straight into a numpy matrix with no parse
step, which is what the brute-force search in services/vector_store.py wants.
"""

from __future__ import annotations

import uuid

import numpy as np

from app.db import Database
from app.models import Chunk, EmbeddedChunk, utc_now_iso

VECTOR_DTYPE = np.float32


def new_chunk_id() -> str:
    return f"chk_{uuid.uuid4().hex[:12]}"


def encode_vector(vector) -> bytes:
    return np.asarray(vector, dtype=VECTOR_DTYPE).tobytes()


def decode_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=VECTOR_DTYPE)


def replace_for_item(db: Database, item_id: str, embedded: list[EmbeddedChunk]) -> int:
    """Swap in a fresh set of chunks for an item, atomically.

    Re-ingesting the same item must never leave a half-old, half-new index,
    so the delete and the insert share one transaction.
    """
    now = utc_now_iso()
    rows = [
        (
            chunk.chunk.id,
            item_id,
            chunk.chunk.ordinal,
            chunk.chunk.text,
            chunk.chunk.char_start,
            chunk.chunk.char_end,
            encode_vector(chunk.embedding),
            len(chunk.embedding),
            chunk.embedding_model,
            now,
        )
        for chunk in embedded
    ]
    with db.write() as conn:
        conn.execute("DELETE FROM chunks WHERE item_id = ?", (item_id,))
        if rows:
            conn.executemany(
                "INSERT INTO chunks (id, item_id, ordinal, text, char_start, char_end, embedding, "
                "embedding_dim, embedding_model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    return len(rows)


def load_searchable(db: Database, item_ids: list[str] | None = None) -> list[dict]:
    """Load every chunk of every ready item, joined with the metadata a
    citation needs. Returned as plain dicts to keep the hot path allocation-light."""
    params: list[object] = []
    filters = ["items.status = 'ready'"]
    if item_ids:
        filters.append(f"chunks.item_id IN ({','.join('?' for _ in item_ids)})")
        params.extend(item_ids)

    sql = (
        "SELECT chunks.id, chunks.item_id, chunks.ordinal, chunks.text, chunks.embedding, "
        "       items.title AS item_title, items.source_type AS item_source_type, "
        "       items.source_url AS item_source_url "
        "FROM chunks JOIN items ON items.id = chunks.item_id "
        f"WHERE {' AND '.join(filters)} "
        "ORDER BY chunks.item_id, chunks.ordinal"
    )
    return [dict(row) for row in db.connection.execute(sql, params).fetchall()]


def for_item(db: Database, item_id: str) -> list[Chunk]:
    rows = db.connection.execute(
        "SELECT id, item_id, ordinal, text, char_start, char_end FROM chunks "
        "WHERE item_id = ? ORDER BY ordinal",
        (item_id,),
    ).fetchall()
    return [
        Chunk(
            id=row["id"],
            item_id=row["item_id"],
            ordinal=row["ordinal"],
            text=row["text"],
            char_start=row["char_start"],
            char_end=row["char_end"],
        )
        for row in rows
    ]


def count(db: Database) -> int:
    return db.connection.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]


def embedding_models_in_use(db: Database) -> list[str]:
    """Used to warn when the index mixes vectors from different models,
    whose scores are not comparable."""
    rows = db.connection.execute("SELECT DISTINCT embedding_model FROM chunks").fetchall()
    return [row["embedding_model"] for row in rows]
