"""Persistence for saved items. No business rules live here."""

from __future__ import annotations

import uuid

from app.db import Database
from app.models import Item, utc_now_iso

_COLUMNS = (
    "id, source_type, title, source_url, raw_content, status, error_message, "
    "char_count, chunk_count, created_at, updated_at"
)


def new_item_id() -> str:
    return f"itm_{uuid.uuid4().hex[:12]}"


def _to_item(row) -> Item:
    return Item(
        id=row["id"],
        source_type=row["source_type"],
        title=row["title"],
        source_url=row["source_url"],
        raw_content=row["raw_content"],
        status=row["status"],
        error_message=row["error_message"],
        char_count=row["char_count"],
        chunk_count=row["chunk_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create(
    db: Database,
    *,
    source_type: str,
    title: str,
    source_url: str | None,
    raw_content: str = "",
    status: str = "pending",
) -> Item:
    now = utc_now_iso()
    item_id = new_item_id()
    with db.write() as conn:
        conn.execute(
            "INSERT INTO items (id, source_type, title, source_url, raw_content, status, "
            "error_message, char_count, chunk_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 0, ?, ?)",
            (item_id, source_type, title, source_url, raw_content, status, len(raw_content), now, now),
        )
    return Item(
        id=item_id,
        source_type=source_type,
        title=title,
        source_url=source_url,
        raw_content=raw_content,
        status=status,
        error_message=None,
        char_count=len(raw_content),
        chunk_count=0,
        created_at=now,
        updated_at=now,
    )


def get(db: Database, item_id: str) -> Item | None:
    row = db.connection.execute(f"SELECT {_COLUMNS} FROM items WHERE id = ?", (item_id,)).fetchone()
    return _to_item(row) if row else None


def list_items(
    db: Database,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    source_type: str | None = None,
) -> tuple[list[Item], int]:
    filters: list[str] = []
    params: list[object] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    if source_type:
        filters.append("source_type = ?")
        params.append(source_type)
    where = f" WHERE {' AND '.join(filters)}" if filters else ""

    total = db.connection.execute(f"SELECT COUNT(*) AS n FROM items{where}", params).fetchone()["n"]
    rows = db.connection.execute(
        f"SELECT {_COLUMNS} FROM items{where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_to_item(row) for row in rows], total


def mark_processing(db: Database, item_id: str) -> None:
    with db.write() as conn:
        conn.execute(
            "UPDATE items SET status = 'processing', error_message = NULL, updated_at = ? WHERE id = ?",
            (utc_now_iso(), item_id),
        )


def mark_ready(db: Database, item_id: str, *, title: str, raw_content: str, chunk_count: int) -> None:
    with db.write() as conn:
        conn.execute(
            "UPDATE items SET status = 'ready', title = ?, raw_content = ?, char_count = ?, "
            "chunk_count = ?, error_message = NULL, updated_at = ? WHERE id = ?",
            (title, raw_content, len(raw_content), chunk_count, utc_now_iso(), item_id),
        )


def mark_failed(db: Database, item_id: str, message: str) -> None:
    with db.write() as conn:
        conn.execute(
            "UPDATE items SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
            (message[:500], utc_now_iso(), item_id),
        )


def delete(db: Database, item_id: str) -> bool:
    with db.write() as conn:
        cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return cursor.rowcount > 0


def count(db: Database) -> int:
    return db.connection.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]


def existing_ids(db: Database, item_ids: list[str]) -> set[str]:
    if not item_ids:
        return set()
    placeholders = ",".join("?" for _ in item_ids)
    rows = db.connection.execute(f"SELECT id FROM items WHERE id IN ({placeholders})", item_ids).fetchall()
    return {row["id"] for row in rows}
