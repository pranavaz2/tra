"""Sharing application queries."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class GetCollaborationQuery:
    """Query to fetch collaboration details for a trip."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class ListMembersQuery:
    """Query to list members of a collaboration with cursor-based pagination."""

    trip_id: str
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))


@dataclass(frozen=True)
class ListInvitationsQuery:
    """Query to list invitations for a collaboration."""

    trip_id: str
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))


@dataclass(frozen=True)
class GetPublicTripQuery:
    """Query to retrieve a publicly shared trip by share token (no auth required)."""

    token: str
