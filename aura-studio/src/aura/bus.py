"""Live event delivery: Redis pub/sub in production, an in-process bus for
keyless dev and tests (where API and worker share one process). Postgres owns
history/replay; the bus only carries the live tail."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from typing import AsyncIterator


class LocalBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, project_id: str, payload: dict) -> None:
        for q in list(self._subs.get(project_id, [])):
            q.put_nowait(payload)

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[project_id].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs[project_id].remove(q)


class RedisBus:
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url)

    @staticmethod
    def _channel(project_id: str) -> str:
        return f"aura:events:{project_id}"

    async def publish(self, project_id: str, payload: dict) -> None:
        await self._redis.publish(self._channel(project_id), json.dumps(payload))

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel(project_id))
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(self._channel(project_id))
                await pubsub.aclose()


_local_bus: LocalBus | None = None


def get_bus(redis_url: str | None):
    if redis_url:
        return RedisBus(redis_url)
    global _local_bus
    if _local_bus is None:
        _local_bus = LocalBus()
    return _local_bus
