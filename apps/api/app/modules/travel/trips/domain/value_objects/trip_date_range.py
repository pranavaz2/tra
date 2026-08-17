"""TripDateRange — departure and optional return date for a trip."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class TripDateRange(ValueObject):
    """
    Immutable date range for a trip.

    Attributes:
        departure_date: The first day of the trip.
        return_date:    The last day of the trip, or None for open-ended trips.
        is_flexible:    True when the user has not committed to exact dates.

    Invariant: return_date, when provided, must be >= departure_date.

    Raises:
        ValidationError: if return_date is earlier than departure_date.
    """

    departure_date: date
    return_date: date | None = None
    is_flexible: bool = False

    def __post_init__(self) -> None:
        if self.return_date is not None and self.return_date < self.departure_date:
            raise ValidationError(
                "Return date must be on or after the departure date.",
                field="return_date",
                value=str(self.return_date),
            )

    @property
    def duration_days(self) -> int | None:
        """Number of calendar days (inclusive) between departure and return, or None."""
        if self.return_date is None:
            return None
        return (self.return_date - self.departure_date).days + 1

    @property
    def is_open_ended(self) -> bool:
        """True when no return date has been set."""
        return self.return_date is None
