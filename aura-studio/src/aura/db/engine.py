"""Async engine/session factory. One Postgres in production (app tables +
LangGraph checkpoints); sqlite+aiosqlite for keyless local dev and tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from aura.db.models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str) -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None or str(_engine.url) != database_url:
        _engine = create_async_engine(database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    get_engine(database_url)
    assert _sessionmaker is not None
    return _sessionmaker


async def init_db(database_url: str) -> None:
    """Create app tables. Dev/test convenience and first-boot bootstrap;
    production schema changes go through Alembic migrations."""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine, _sessionmaker = None, None
