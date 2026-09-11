"""Application settings, loaded once from the environment.

Everything tunable lives here so behaviour can be changed without touching
call sites, and so tests can point the app at a temporary database.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "inbox.db"


def _env_str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value if value not in (None, "") else default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {raw!r}") from exc


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of configuration for one process."""

    # --- storage ---------------------------------------------------------
    database_path: Path = field(default_factory=lambda: Path(_env_str("DATABASE_PATH", str(DEFAULT_DB_PATH))))

    # --- providers -------------------------------------------------------
    # "auto" resolves to openai/anthropic when a key is present, else "local".
    embedding_provider: str = field(default_factory=lambda: _env_str("EMBEDDING_PROVIDER", "auto"))
    llm_provider: str = field(default_factory=lambda: _env_str("LLM_PROVIDER", "auto"))
    openai_api_key: str = field(default_factory=lambda: _env_str("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: _env_str("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_embedding_model: str = field(
        default_factory=lambda: _env_str("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    openai_chat_model: str = field(default_factory=lambda: _env_str("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    anthropic_api_key: str = field(default_factory=lambda: _env_str("ANTHROPIC_API_KEY", ""))
    anthropic_base_url: str = field(default_factory=lambda: _env_str("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    anthropic_model: str = field(default_factory=lambda: _env_str("ANTHROPIC_MODEL", "claude-sonnet-5"))
    local_embedding_dim: int = field(default_factory=lambda: _env_int("LOCAL_EMBEDDING_DIM", 1024))
    provider_timeout_seconds: float = field(default_factory=lambda: _env_float("PROVIDER_TIMEOUT_SECONDS", 30.0))

    # --- chunking --------------------------------------------------------
    chunk_target_chars: int = field(default_factory=lambda: _env_int("CHUNK_TARGET_CHARS", 900))
    chunk_overlap_chars: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP_CHARS", 150))
    chunk_min_chars: int = field(default_factory=lambda: _env_int("CHUNK_MIN_CHARS", 120))

    # --- retrieval -------------------------------------------------------
    retrieval_top_k: int = field(default_factory=lambda: _env_int("RETRIEVAL_TOP_K", 5))
    retrieval_candidate_k: int = field(default_factory=lambda: _env_int("RETRIEVAL_CANDIDATE_K", 20))
    retrieval_min_score: float = field(default_factory=lambda: _env_float("RETRIEVAL_MIN_SCORE", 0.12))
    # Weight of dense (vector) score in the hybrid blend; the remainder is lexical.
    retrieval_dense_weight: float = field(default_factory=lambda: _env_float("RETRIEVAL_DENSE_WEIGHT", 0.7))
    max_chunks_per_item_in_context: int = field(default_factory=lambda: _env_int("MAX_CHUNKS_PER_ITEM_IN_CONTEXT", 3))

    # --- ingestion limits ------------------------------------------------
    max_note_chars: int = field(default_factory=lambda: _env_int("MAX_NOTE_CHARS", 200_000))
    max_fetch_bytes: int = field(default_factory=lambda: _env_int("MAX_FETCH_BYTES", 2_000_000))
    fetch_timeout_seconds: float = field(default_factory=lambda: _env_float("FETCH_TIMEOUT_SECONDS", 10.0))
    fetch_max_redirects: int = field(default_factory=lambda: _env_int("FETCH_MAX_REDIRECTS", 5))
    allow_private_network_fetch: bool = field(default_factory=lambda: _env_bool("ALLOW_PRIVATE_NETWORK_FETCH", False))
    user_agent: str = field(default_factory=lambda: _env_str("FETCH_USER_AGENT", "AIKnowledgeInbox/1.0 (+https://github.com/AmeyBhat190102)"))

    # --- server ----------------------------------------------------------
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in _env_str("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if origin.strip()
        )
    )
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO").upper())
    log_format: str = field(default_factory=lambda: _env_str("LOG_FORMAT", "json"))
    ingest_worker_count: int = field(default_factory=lambda: _env_int("INGEST_WORKER_COUNT", 2))

    def __post_init__(self) -> None:
        if self.chunk_overlap_chars >= self.chunk_target_chars:
            raise ValueError("CHUNK_OVERLAP_CHARS must be smaller than CHUNK_TARGET_CHARS")
        if not 0.0 <= self.retrieval_dense_weight <= 1.0:
            raise ValueError("RETRIEVAL_DENSE_WEIGHT must be between 0 and 1")
        if self.retrieval_top_k < 1:
            raise ValueError("RETRIEVAL_TOP_K must be at least 1")

    def resolved_embedding_provider(self) -> str:
        if self.embedding_provider != "auto":
            return self.embedding_provider
        return "openai" if self.openai_api_key else "local"

    def resolved_llm_provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Drop the cached settings so tests can re-read a patched environment."""
    get_settings.cache_clear()
