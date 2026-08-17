"""Media application queries."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class GetMediaQuery:
    """Query to retrieve a single media item by ID."""

    trip_id: str
    media_id: str
    requester_id: str


@dataclass(frozen=True)
class ListMediaQuery:
    """Query to list all media items in a collection with cursor pagination."""

    trip_id: str
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))


@dataclass(frozen=True)
class GetMediaByActivityQuery:
    """Query to retrieve all media items attached to a specific activity."""

    trip_id: str
    activity_id: str
    requester_id: str


@dataclass(frozen=True)
class GetMediaByExpenseQuery:
    """Query to retrieve all media items attached to a specific expense."""

    trip_id: str
    expense_id: str
    requester_id: str
