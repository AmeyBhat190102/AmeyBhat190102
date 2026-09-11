"""SQLite access: connection management, schema, and a tiny async bridge.

SQLite is the whole persistence layer here: rows for items/chunks and BLOBs
for embedding vectors. One store means one thing to run and one thing to
back up, which is the right trade at single-user scale.

Connections are thread-local because sqlite3 connections are not safe to
share across threads, and the async bridge (`run_db`) hands blocking calls
to a worker thread so the event loop keeps serving requests.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    source_type   TEXT NOT NULL CHECK (source_type IN ('note', 'url')),
    title         TEXT NOT NULL,
    source_url    TEXT,
    raw_content   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    error_message TEXT,
    char_count    INTEGER NOT NULL DEFAULT 0,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_created_at ON items (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_status ON items (status);

CREATE TABLE IF NOT EXISTS chunks (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    ordinal         INTEGER NOT NULL,
    text            TEXT NOT NULL,
    char_start      INTEGER NOT NULL,
    char_end        INTEGER NOT NULL,
    embedding       BLOB NOT NULL,
    embedding_dim   INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE (item_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks (item_id);
"""


class Database:
    """Owns the SQLite file and hands out per-thread connections."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self._write_lock = threading.Lock()

    def _new_connection(self) -> sqlite3.Connection:
        if self.path.parent and str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._new_connection()
            self._local.conn = conn
        return conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Run a write transaction. SQLite allows exactly one writer, so a
        process-level lock keeps concurrent ingest jobs from colliding."""
        conn = self.connection
        with self._write_lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)
        logger.info("database ready", extra={"database_path": str(self.path)})

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


_database: Database | None = None
_database_lock = threading.Lock()


def get_database(path: Path | str | None = None) -> Database:
    """Return the process-wide database, creating it on first use."""
    global _database
    with _database_lock:
        if _database is None:
            if path is None:
                from app.config import get_settings

                path = get_settings().database_path
            _database = Database(path)
            _database.initialize()
        return _database


def reset_database(path: Path | str | None = None) -> Database:
    """Point the process at a fresh database. Used by tests."""
    global _database
    with _database_lock:
        if _database is not None:
            _database.close()
        _database = None
    return get_database(path)


async def run_db(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute a blocking repository call off the event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)
