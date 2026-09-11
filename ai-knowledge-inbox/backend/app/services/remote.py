"""One place for outbound provider HTTP calls.

Both the embedding and the LLM clients need the same things: a timeout, a
bounded retry on transient failures, and a translation from transport errors
into a single application error type. Keeping that here stops the retry logic
from being copy-pasted into every client.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.errors import ProviderError
from app.logging_config import get_logger

logger = get_logger(__name__)

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


async def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    provider: str,
    attempts: int = 3,
    backoff_seconds: float = 0.5,
) -> dict[str, Any]:
    """POST JSON and return the decoded body, retrying transient failures."""
    last_error: str = "unknown error"

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException:
                last_error = f"{provider} timed out after {timeout}s"
            except httpx.HTTPError as exc:
                last_error = f"{provider} request failed: {exc}"
            else:
                if response.status_code < 400:
                    return response.json()
                last_error = f"{provider} returned {response.status_code}: {response.text[:300]}"
                if response.status_code not in RETRYABLE_STATUS:
                    raise ProviderError(
                        last_error,
                        details={"provider": provider, "status_code": response.status_code},
                    )

            if attempt < attempts:
                delay = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "provider call failed, retrying",
                    extra={"provider": provider, "attempt": attempt, "retry_in_s": delay, "reason": last_error},
                )
                await asyncio.sleep(delay)

    raise ProviderError(last_error, details={"provider": provider, "attempts": attempts})
