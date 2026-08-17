"""
Trip application commands.

Immutable value objects that cross the boundary from the presentation layer
into the application layer. Commands carry raw, unvalidated input — the
TripService is responsible for all validation and domain enrichment.

Design:
  - All fields are primitives (str, date, bool) so the presentation layer
    has no dependency on domain value objects.
  - IDs are raw UUID strings; the service parses and validates them.
  - Enum strings ('privacy', 'new_status') are raw; the service converts
    them to domain enum types.
  - UpdateTripCommand uses explicit None to mean "do not change this field".
    The update_dates flag distinguishes "clear the date range" (update_dates=True,
    departure_date=None) from "don't touch dates" (update_dates=False).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CreateTripCommand:
    """
    Command to create a new trip.

    Attributes:
        owner_id:        UUID string of the authenticated user creating the trip.
        title:           Human-readable trip name. Validated by the service
                         (1–100 chars after stripping whitespace).
        privacy:         Visibility setting. Must be a valid TripPrivacy value:
                         'private' | 'link_only' | 'public'. Defaults to 'private'.
        departure_date:  Optional first day of the trip. When None, the trip
                         is created without a scheduled date range.
        return_date:     Optional last day of the trip. When provided,
                         departure_date must also be provided and return_date
                         must be >= departure_date.
        is_date_flexible: True when the user has not committed to exact dates.
    """

    owner_id: str
    title: str
    privacy: str = "private"
    departure_date: date | None = None
    return_date: date | None = None
    is_date_flexible: bool = False


@dataclass(frozen=True)
class UpdateTripCommand:
    """
    Command to update one or more mutable fields of an existing trip.

    Only fields that are explicitly set will be applied. The update_dates
    flag distinguishes "change the date range" from "do not touch dates":

        update_dates=False → date range unchanged (ignore departure/return/flexible)
        update_dates=True, departure_date=None → clear the date range
        update_dates=True, departure_date=<date> → set a new date range

    Status transitions follow the domain rules in TripStatus. Invalid
    transitions return Failure(InvalidTripStatusTransitionError).

    Attributes:
        trip_id:          UUID string of the trip to update.
        requester_id:     UUID string of the authenticated user. Must match
                          the trip's owner_id (authorization enforced by service).
        title:            New trip name. None = do not change.
        privacy:          New visibility value. None = do not change.
        new_status:       Target lifecycle status. None = do not change.
                          Must be a valid TripStatus value and a permitted
                          transition from the current status.
        update_dates:     When True, apply the departure_date / return_date /
                          is_date_flexible fields. When False, dates are unchanged.
        departure_date:   New departure date. Only read when update_dates=True.
                          None when update_dates=True clears the date range.
        return_date:      New return date. Only read when update_dates=True.
        is_date_flexible: New flexibility flag. Only read when update_dates=True.
    """

    trip_id: str
    requester_id: str
    title: str | None = None
    privacy: str | None = None
    new_status: str | None = None
    update_dates: bool = False
    departure_date: date | None = None
    return_date: date | None = None
    is_date_flexible: bool = False


@dataclass(frozen=True)
class DeleteTripCommand:
    """
    Command to soft-delete a trip.

    The trip is marked as deleted (deleted_at set to now) and a TripDeleted
    event is emitted. The record is NOT physically removed — use the GDPR
    erasure endpoint (hard delete via ITripRepository.delete()) for that.

    The service returns Failure(TripNotFoundError) if the trip is already
    deleted. Deleting a trip that does not exist also returns TripNotFoundError.

    Attributes:
        trip_id:      UUID string of the trip to soft-delete.
        requester_id: UUID string of the authenticated user. Must match the
                      trip's owner_id.
    """

    trip_id: str
    requester_id: str
