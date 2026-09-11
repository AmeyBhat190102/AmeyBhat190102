"""Structured logging.

Every log line is a single JSON object so it can be shipped to any log
aggregator without a custom parser. A per-request id is carried in a
ContextVar, so nested service calls are correlated without threading a
logger argument through every function signature.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Attributes LogRecord always carries; anything else was passed via `extra`
# and therefore belongs in the structured payload.
_RESERVED_RECORD_KEYS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"asctime", "message", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-friendly formatter for local development (LOG_FORMAT=console)."""

    def format(self, record: logging.LogRecord) -> str:
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_KEYS
        }
        suffix = " " + " ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""
        base = f"{record.levelname:<7} [{request_id_var.get()}] {record.name}: {record.getMessage()}{suffix}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Install a single stdout handler on the root logger (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else ConsoleFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn ships its own handlers; let records bubble up to ours instead
    # so that access and application logs share one format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
