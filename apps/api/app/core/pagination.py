"""
Travix AI — Cursor-Based Pagination

Shared pagination utilities for all collection endpoints.

Why cursor-based (not offset-based)?
  - Stable results: inserting new items while the client pages does not
    cause items to be skipped or returned twice.
  - Efficient: uses an indexed WHERE clause instead of OFFSET, which
    performs a full scan of skipped rows at the database level.
  - Suitable for infinite-scroll UIs common in mobile travel apps.

Usage — in a schema:
    from app.core.pagination import CursorPage, DEFAULT_PAGE_SIZE

    class TripListResponse(BaseModel):
        items: list[TripResponse]
        pagination: CursorPage

Usage — in a repository:
    from app.core.pagination import decode_cursor, encode_cursor, DEFAULT_PAGE_SIZE

    async def list_trips(cursor: str | None, limit: int) -> tuple[list[Trip], str | None]:
        decoded_id = decode_cursor(cursor) if cursor else None
        # Build query: WHERE id > decoded_id ORDER BY id LIMIT limit+1
        rows = ...
        next_cursor = encode_cursor(str(rows[-1].id)) if len(rows) > limit else None
        return rows[:limit], next_cursor

Cursor encoding:
  The cursor is the base64url encoding of the last-seen item's sort key
  (typically a UUID or timestamp string). This is opaque to the client —
  clients must not parse or construct cursor values.
"""

from __future__ import annotations

import base64
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, model_config

T = TypeVar("T")

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100


# ---------------------------------------------------------------------------
# Cursor encoding / decoding
# ---------------------------------------------------------------------------


def encode_cursor(value: str) -> str:
    """
    Encode a sort-key value as a URL-safe base64 cursor token.

    Args:
        value: The raw sort-key value (e.g. a UUID string or ISO timestamp).

    Returns:
        A URL-safe base64 string safe to include in JSON responses.
    """
    return base64.urlsafe_b64encode(value.encode()).decode()


def decode_cursor(cursor: str) -> str:
    """
    Decode a cursor token back to the original sort-key value.

    Args:
        cursor: A cursor token previously returned by encode_cursor().

    Returns:
        The original sort-key value.

    Raises:
        ValueError: If the cursor is not valid base64url-encoded data.
    """
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode()
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {cursor!r}") from exc


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class PaginationMeta(BaseModel):
    """Pagination metadata included in every collection response."""

    model_config = model_config(populate_by_name=True)

    next_cursor: str | None = Field(
        default=None,
        description=(
            "Opaque cursor token for the next page. "
            "Pass as ?cursor=<value> to retrieve the next batch. "
            "Null when this is the last page."
        ),
    )
    limit: int = Field(description="Maximum number of items returned per page.")
    has_more: bool = Field(description="True if there are more items after this page.")


class CursorPage(BaseModel, Generic[T]):
    """
    Generic paginated collection response.

    Type parameter T is the item schema. Concrete usage:

        class TripListResponse(BaseModel):
            items: list[TripResponse]
            pagination: CursorPage[TripResponse]

    Or as a standalone response model:

        @router.get("/trips", response_model=CursorPage[TripResponse])
        async def list_trips(...) -> CursorPage[TripResponse]:
            ...
    """

    model_config = model_config(populate_by_name=True)

    items: list[T] = Field(description="The items on this page.")
    pagination: PaginationMeta


def make_page(
    items: list[T],
    *,
    limit: int,
    next_cursor: str | None,
) -> CursorPage[T]:
    """
    Construct a CursorPage from a list of items and pagination state.

    Args:
        items: The items to include in this page.
        limit: The limit that was requested (used to compute has_more).
        next_cursor: The encoded cursor for the next page, or None if last page.
    """
    return CursorPage(
        items=items,
        pagination=PaginationMeta(
            next_cursor=next_cursor,
            limit=limit,
            has_more=next_cursor is not None,
        ),
    )
