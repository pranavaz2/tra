"""
Trip application queries.

Immutable value objects that represent read-only operations. Queries carry
only the parameters needed to retrieve data and the requester's identity
for authorization. They never mutate state.

Queries are structurally separate from commands (CQRS) to make the
read/write asymmetry explicit. Handlers dispatch queries to the TripService
read methods; command handlers dispatch commands to the write methods.

Cursor:
  ListTripsQuery.cursor is a base64url-encoded TripId string returned by
  a previous ListTripsQuery response. The service decodes it; the
  presentation layer treats it as an opaque token and must not parse it.

Status filter:
  ListTripsQuery.status_filter is an optional raw TripStatus string value.
  When provided, only trips in that status are returned. The service
  validates the value against the TripStatus enum.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class GetTripQuery:
    """
    Query to load a single trip by ID.

    The service returns Failure(TripNotFoundError) if the trip does not
    exist or has been soft-deleted. It returns Failure(ForbiddenError) if
    requester_id does not match the trip's owner_id.

    Future: when collaborative trips are introduced, this will also allow
    access by users who hold a TripCollaboration record for the trip.

    Attributes:
        trip_id:      UUID string of the trip to retrieve.
        requester_id: UUID string of the authenticated user.
    """

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class ListTripsQuery:
    """
    Query to list a user's trips with cursor-based pagination.

    Returns only non-deleted trips owned by owner_id. Results are ordered
    newest-first (created_at DESC, trip_id DESC).

    The requester must be the same as the owner. Future: admin roles and
    collaborative access will allow other requesters.

    Attributes:
        owner_id:       UUID string of the user whose trips to list.
        requester_id:   UUID string of the authenticated user. Must match
                        owner_id for the current authorization model.
        limit:          Maximum number of trips per page. Clamped to
                        [1, MAX_PAGE_SIZE]. Defaults to DEFAULT_PAGE_SIZE.
        cursor:         Opaque cursor token from a previous response's
                        next_cursor field. None retrieves the first page.
        status_filter:  When provided, restrict results to trips in this
                        lifecycle status. Must be a valid TripStatus value.
                        None returns trips in all statuses.
    """

    owner_id: str
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None
    status_filter: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))
