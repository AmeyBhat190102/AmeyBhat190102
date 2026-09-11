"""Application error types and their HTTP representation.

Services raise these instead of HTTPException so that business logic stays
free of web-framework imports; a single handler in main.py turns them into
responses with a stable JSON error shape:

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for errors that map onto a known HTTP response."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class ValidationError(AppError):
    """Input was syntactically valid JSON but semantically unusable."""

    status_code = 400
    code = "invalid_request"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UnsupportedContentError(AppError):
    """The URL resolved to something we cannot turn into text (PDF, image...)."""

    status_code = 415
    code = "unsupported_content"


class ContentTooLargeError(AppError):
    status_code = 413
    code = "content_too_large"


class FetchError(AppError):
    """A remote URL could not be retrieved; the caller's request was fine."""

    status_code = 502
    code = "fetch_failed"


class ProviderError(AppError):
    """An embedding or LLM provider failed or is misconfigured."""

    status_code = 503
    code = "provider_unavailable"
