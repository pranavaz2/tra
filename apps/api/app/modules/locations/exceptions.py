"""Module-specific exceptions for locations."""

from __future__ import annotations


class LocationError(Exception):
    """Base class for locations module errors."""


class LocationNotFoundError(LocationError):
    """Raised when a requested location does not exist or is deleted."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__("Location was not found.")


class InvalidLocationQueryError(LocationError):
    """Raised when a location search query is invalid."""

    def __init__(self) -> None:
        super().__init__("Location query must not be empty.")
