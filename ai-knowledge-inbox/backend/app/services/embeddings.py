"""Embedding providers.

Two implementations behind one interface:

* OpenAIEmbeddings  - real semantic embeddings, used when OPENAI_API_KEY is set.
* LocalHashingEmbeddings - deterministic, offline, zero-dependency fallback so
  the app runs and the tests pass without an API key or network access.

The local provider uses the hashing trick over stemmed tokens. Cosine
similarity between two such vectors approximates weighted term overlap: good
enough to demonstrate and test the pipeline, but it does not capture synonymy.
That gap is partly covered by the lexical half of the hybrid retrieval score
and is called out in /health so nobody mistakes it for a semantic index.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.config import Settings, get_settings
from app.errors import ProviderError
from app.logging_config import get_logger
from app.services.remote import post_json
from app.services.text import stem, tokenize

logger = get_logger(__name__)

OPENAI_BATCH_SIZE = 64


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


class LocalHashingEmbeddings:
    """Feature-hashed bag of stemmed tokens, L2 normalized."""

    name = "local"

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions < 32:
            raise ValueError("local embedding dimensions must be at least 32")
        self.dimensions = dimensions
        self.model = f"local-hashing-{dimensions}"

    def _feature_slot(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        # One bit picks the sign, so unrelated features that collide tend to
        # cancel instead of always reinforcing each other.
        return value % self.dimensions, 1.0 if (value >> 63) & 1 else -1.0

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        if not tokens:
            return vector

        counts = Counter(stem(token) for token in tokens)
        for feature, count in counts.items():
            # Sublinear term frequency: the tenth mention of a word says much
            # less than the second.
            weight = 1.0 + math.log(count)
            slot, sign = self._feature_slot(feature)
            vector[slot] += sign * weight
        return _l2_normalize(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self.embed_one(text)


class OpenAIEmbeddings:
    """Client for the OpenAI /embeddings endpoint."""

    name = "openai"
    _MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ProviderError(
                "OPENAI_API_KEY is not set; set it or use EMBEDDING_PROVIDER=local",
                details={"provider": "openai"},
            )
        self.model = settings.openai_embedding_model
        self.dimensions = self._MODEL_DIMENSIONS.get(self.model, 1536)
        self._url = f"{settings.openai_base_url.rstrip('/')}/embeddings"
        self._headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = settings.provider_timeout_seconds

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        body = await post_json(
            self._url,
            headers=self._headers,
            payload={"model": self.model, "input": texts},
            timeout=self._timeout,
            provider="openai-embeddings",
        )
        try:
            ordered = sorted(body["data"], key=lambda row: row["index"])
            return [row["embedding"] for row in ordered]
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                "unexpected embedding response shape from OpenAI",
                details={"provider": "openai-embeddings"},
            ) from exc

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), OPENAI_BATCH_SIZE):
            batch = texts[start : start + OPENAI_BATCH_SIZE]
            vectors.extend(await self._embed_batch(batch))
            logger.info(
                "embedded batch",
                extra={"provider": self.name, "model": self.model, "batch_size": len(batch)},
            )
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed_batch([text]))[0]


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    choice = settings.resolved_embedding_provider()
    if choice == "openai":
        return OpenAIEmbeddings(settings)
    if choice == "local":
        return LocalHashingEmbeddings(settings.local_embedding_dim)
    raise ProviderError(
        f"unknown embedding provider {choice!r}; expected 'openai', 'local' or 'auto'",
        details={"provider": choice},
    )


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    provider = build_embedding_provider(get_settings())
    logger.info(
        "embedding provider ready",
        extra={"provider": provider.name, "model": provider.model, "dimensions": provider.dimensions},
    )
    return provider


def reset_embedding_provider_cache() -> None:
    get_embedding_provider.cache_clear()
