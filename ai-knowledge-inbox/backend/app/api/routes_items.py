"""Item endpoints: create, list, read, delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import DatabaseDep, QueueDep, SettingsDep, VectorStoreDep
from app.db import run_db
from app.errors import NotFoundError
from app.logging_config import get_logger
from app.models import Item
from app.repositories import items as item_repo
from app.schemas import (
    ErrorResponse,
    IngestRequest,
    ItemDetailResponse,
    ItemListResponse,
    ItemResponse,
    ItemStatus,
    SourceType,
)
from app.services.ingestion import create_pending_item

logger = get_logger(__name__)

router = APIRouter(tags=["items"])

MAX_PAGE_SIZE = 100


def to_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        source_type=item.source_type,
        title=item.title,
        source_url=item.source_url,
        status=item.status,
        error_message=item.error_message,
        char_count=item.char_count,
        chunk_count=item.chunk_count,
        preview=item.preview(),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "/ingest",
    response_model=ItemResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Save a note or a URL",
)
async def ingest(
    payload: IngestRequest,
    db: DatabaseDep,
    settings: SettingsDep,
    queue: QueueDep,
) -> ItemResponse:
    """Accept content and queue it for processing.

    Returns 202 rather than 201: the row exists, but fetching and embedding
    happen on a worker, so the item is not searchable until its status
    reaches `ready`.
    """
    item = await run_db(create_pending_item, db, payload, settings)
    await queue.submit(item.id)
    logger.info(
        "item queued",
        extra={"item_id": item.id, "source_type": item.source_type, "queue_depth": queue.pending},
    )
    return to_response(item)


@router.get("/items", response_model=ItemListResponse, summary="List saved items, newest first")
async def list_items(
    db: DatabaseDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    item_status: Annotated[ItemStatus | None, Query(alias="status")] = None,
    source_type: Annotated[SourceType | None, Query()] = None,
) -> ItemListResponse:
    items, total = await run_db(
        item_repo.list_items,
        db,
        limit=limit,
        offset=offset,
        status=item_status,
        source_type=source_type,
    )
    return ItemListResponse(
        items=[to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/items/{item_id}",
    response_model=ItemDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Read one item, including its full text",
)
async def get_item(item_id: str, db: DatabaseDep) -> ItemDetailResponse:
    item = await run_db(item_repo.get, db, item_id)
    if item is None:
        raise NotFoundError(f"no item with id {item_id!r}", details={"item_id": item_id})
    return ItemDetailResponse(**to_response(item).model_dump(), raw_content=item.raw_content)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete an item and its chunks",
)
async def delete_item(item_id: str, db: DatabaseDep, store: VectorStoreDep) -> None:
    deleted = await run_db(item_repo.delete, db, item_id)
    if not deleted:
        raise NotFoundError(f"no item with id {item_id!r}", details={"item_id": item_id})
    store.invalidate()
    logger.info("item deleted", extra={"item_id": item_id})
