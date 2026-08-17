"""Itinerary-specific domain and application errors."""

from __future__ import annotations

from app.shared.domain.errors import ApplicationError, DomainError


class ItineraryNotFoundError(ApplicationError):
    """No itinerary exists with the given ID or Trip ID."""

    code = "itinerary_not_found"

    def __init__(self, key: str) -> None:
        super().__init__(f"Itinerary for '{key}' not found.")
        self.key = key


class ItineraryAlreadyExistsError(DomainError):
    """An itinerary already exists for the given Trip."""

    code = "itinerary_already_exists"

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Itinerary for trip '{trip_id}' already exists.")
        self.trip_id = trip_id


class ItineraryAlreadyDeletedError(DomainError):
    """The itinerary has already been soft-deleted."""

    code = "itinerary_already_deleted"

    def __init__(self) -> None:
        super().__init__("This itinerary has already been deleted.")


class ItineraryDayNotFoundError(DomainError):
    """No day exists with the given ID inside the itinerary."""

    code = "itinerary_day_not_found"

    def __init__(self, day_id: str) -> None:
        super().__init__(f"Itinerary day '{day_id}' not found.")
        self.day_id = day_id


class ItineraryDayAlreadyExistsError(DomainError):
    """A day with the same day number already exists in this itinerary."""

    code = "itinerary_day_already_exists"

    def __init__(self, day_number: int) -> None:
        super().__init__(f"Itinerary day with number '{day_number}' already exists.")
        self.day_number = day_number


class ItineraryItemNotFoundError(DomainError):
    """No item exists with the given ID inside the day/itinerary."""

    code = "itinerary_item_not_found"

    def __init__(self, item_id: str) -> None:
        super().__init__(f"Itinerary item '{item_id}' not found.")
        self.item_id = item_id
