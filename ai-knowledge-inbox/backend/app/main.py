"""Application entry point: app factory, lifespan, error handling.

Composition happens here and nowhere else. Routes know about services,
services know about repositories, and only this module knows about all of
them plus the web framework.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_health, routes_items, routes_query
from app.config import get_settings
from app.db import get_database
from app.errors import AppError
from app.logging_config import configure_logging, get_logger
from app.middleware import RequestContextMiddleware
from app.services.answering import get_answerer
from app.services.embeddings import get_embedding_provider
from app.services.ingestion import process_item
from app.services.jobs import IngestionQueue
from app.services.vector_store import get_vector_store

logger = get_logger(__name__)

API_DESCRIPTION = """
Save notes and URLs, then ask questions answered from that content with citations.

Every error response uses the shape `{"error": {"code", "message", "details"}}`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = get_database()
    store = get_vector_store(database)
    embedder = get_embedding_provider()
    answerer = get_answerer()

    async def handle(item_id: str) -> None:
        await process_item(item_id, db=database, settings=settings, embedder=embedder, store=store)

    queue = IngestionQueue(handle, worker_count=settings.ingest_worker_count)
    await queue.start()
    app.state.ingestion_queue = queue

    logger.info(
        "service started",
        extra={
            "embedding_provider": embedder.name,
            "embedding_model": embedder.model,
            "llm_provider": answerer.name,
            "llm_model": answerer.model,
            "database_path": str(settings.database_path),
        },
    )
    try:
        yield
    finally:
        await queue.stop()
        database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title="AI Knowledge Inbox",
        description=API_DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        logger.warning(
            "request rejected",
            extra={
                "path": request.url.path,
                "code": error.code,
                "status_code": error.status_code,
                "reason": error.message,
            },
        )
        return JSONResponse(status_code=error.status_code, content=error.to_payload())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Flatten pydantic's error list into something a client can show a
        # user directly, keyed by the field that actually failed.
        fields = [
            {
                "field": ".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        logger.warning("request failed validation", extra={"path": request.url.path, "fields": fields})
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "the request body or query string is invalid",
                    "details": {"fields": fields},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _error: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    # Deliberately generic: the detail is in the logs, keyed by
                    # the request id the client already has.
                    "message": "an unexpected error occurred",
                }
            },
        )

    app.include_router(routes_items.router)
    app.include_router(routes_query.router)
    app.include_router(routes_health.router)
    return app


app = create_app()
