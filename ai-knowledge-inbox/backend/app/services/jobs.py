"""In-process ingestion queue.

POST /ingest returns as soon as the item row exists; fetching a URL and
embedding its chunks happens on a worker task. A synchronous ingest would tie
the caller's request to a third-party fetch plus an embedding round trip,
which is both slow and fragile, and it would block the event loop's ability
to serve the item list the UI is polling.

This is deliberately the smallest thing that works for a single-user app: an
asyncio.Queue and a couple of worker tasks. The queue is in memory, so jobs
do not survive a restart; items stuck in `pending` are visible in the UI
rather than silently lost. See the README for what replaces this in
production (a durable queue plus separate workers).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.logging_config import get_logger, request_id_var

logger = get_logger(__name__)

JobHandler = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class Job:
    item_id: str
    request_id: str


class IngestionQueue:
    def __init__(self, handler: JobHandler, *, worker_count: int = 2) -> None:
        self._handler = handler
        self._worker_count = max(1, worker_count)
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    async def start(self) -> None:
        if self._workers:
            return
        self._workers = [
            asyncio.create_task(self._run_worker(index), name=f"ingest-worker-{index}")
            for index in range(self._worker_count)
        ]
        logger.info("ingestion workers started", extra={"workers": self._worker_count})

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("ingestion workers stopped")

    async def submit(self, item_id: str) -> None:
        await self._queue.put(Job(item_id=item_id, request_id=request_id_var.get()))

    async def wait_until_idle(self) -> None:
        """Block until every queued job has finished. Used by tests."""
        await self._queue.join()

    async def _run_worker(self, index: int) -> None:
        while True:
            job = await self._queue.get()
            # Carry the originating request id so ingest logs join up with the
            # POST /ingest that created the job.
            token = request_id_var.set(job.request_id)
            try:
                await self._handler(job.item_id)
            except asyncio.CancelledError:
                self._queue.task_done()
                raise
            except Exception:
                # A failed job must never take the worker down with it; the
                # handler is responsible for recording the failure on the item.
                logger.exception("ingestion job crashed", extra={"item_id": job.item_id, "worker": index})
            else:
                pass
            finally:
                request_id_var.reset(token)
            self._queue.task_done()
