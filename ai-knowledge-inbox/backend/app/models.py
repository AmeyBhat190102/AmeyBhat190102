"""Domain objects passed between layers.

Repositories return these instead of sqlite3.Row so that services and the
API never depend on column names or on the database driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def utc_now_iso() -> str:
    """UTC, microsecond precision.

    Seconds precision was not enough: two items saved in the same second
    compared equal, and the item list fell back to an arbitrary tiebreak.
    """
    return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass(slots=True)
class Item:
    id: str
    source_type: str
    title: str
    source_url: str | None
    raw_content: str
    status: str
    error_message: str | None
    char_count: int
    chunk_count: int
    created_at: str
    updated_at: str

    def preview(self, limit: int = 220) -> str:
        text = " ".join(self.raw_content.split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass(slots=True)
class Chunk:
    """A retrievable slice of an item, with its char offsets into raw_content."""

    id: str
    item_id: str
    ordinal: int
    text: str
    char_start: int
    char_end: int


@dataclass(slots=True)
class EmbeddedChunk:
    chunk: Chunk
    embedding: list[float]
    embedding_model: str


@dataclass(slots=True)
class ScoredChunk:
    """A retrieval hit, carrying enough item metadata to cite it."""

    chunk_id: str
    item_id: str
    item_title: str
    item_source_type: str
    item_source_url: str | None
    ordinal: int
    text: str
    dense_score: float
    lexical_score: float
    score: float
