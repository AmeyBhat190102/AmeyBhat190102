"""Request and response models.

These are the API contract. Validation that can be expressed declaratively
lives here so handlers stay thin and 422s are produced before any work,
any network call, or any token spend happens.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal["note", "url"]
ItemStatus = Literal["pending", "processing", "ready", "failed"]

MAX_TITLE_CHARS = 200
MAX_QUESTION_CHARS = 1_000


class NoteIngestRequest(BaseModel):
    """Ingest a plain-text note."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["note"]
    content: str = Field(min_length=1, max_length=200_000, description="Plain-text body of the note.")
    title: str | None = Field(default=None, max_length=MAX_TITLE_CHARS)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must contain non-whitespace text")
        return value.strip()

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class UrlIngestRequest(BaseModel):
    """Ingest a web page; the server fetches and extracts the text."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["url"]
    url: str = Field(min_length=8, max_length=2_048)
    title: str | None = Field(default=None, max_length=MAX_TITLE_CHARS)

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return candidate

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


IngestRequest = Annotated[NoteIngestRequest | UrlIngestRequest, Field(discriminator="type")]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=MAX_QUESTION_CHARS)
    top_k: int | None = Field(default=None, ge=1, le=20, description="Chunks to place in the LLM context.")
    item_ids: list[str] | None = Field(default=None, max_length=50, description="Restrict retrieval to these items.")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("question must contain at least 3 non-whitespace characters")
        return cleaned


class ItemResponse(BaseModel):
    id: str
    source_type: SourceType
    title: str
    source_url: str | None = None
    status: ItemStatus
    error_message: str | None = None
    char_count: int
    chunk_count: int
    preview: str
    created_at: datetime
    updated_at: datetime


class ItemDetailResponse(ItemResponse):
    raw_content: str


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    limit: int
    offset: int


class Citation(BaseModel):
    """One retrieved chunk, numbered so the answer text can point at it."""

    marker: int = Field(description="1-based marker referenced as [1] in the answer text.")
    chunk_id: str
    item_id: str
    title: str
    source_type: SourceType
    source_url: str | None = None
    snippet: str
    score: float = Field(description="Hybrid relevance score in [0, 1]; higher is better.")


class QueryResponse(BaseModel):
    question: str
    answer: str
    grounded: bool = Field(description="False when nothing relevant was retrieved and no answer was attempted.")
    citations: list[Citation]
    chunks_searched: int
    model: str
    provider: str
    latency_ms: int


class ProviderInfo(BaseModel):
    embeddings: str
    embedding_model: str
    llm: str
    llm_model: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    items: int
    chunks: int
    pending_jobs: int
    providers: ProviderInfo


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    """Every non-2xx response from this API uses this shape."""

    error: ErrorBody
