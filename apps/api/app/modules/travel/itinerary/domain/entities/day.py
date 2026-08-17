"""ItineraryDay entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.shared.domain.entity import Entity
from app.shared.domain.errors import ValidationError


@dataclass(kw_only=True, eq=False)
class ItineraryDay(Entity[ItineraryDayId]):
    """
    ItineraryDay entity inside the Itinerary Aggregate Root boundary.

    Represents a single day of travel, containing multiple scheduled items.
    """

    itinerary_id: ItineraryId
    day_number: int
    title: str | None = None
    date: date | None = None
    items: list[ItineraryItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.day_number < 1:
            raise ValidationError(
                "Day number must be greater than or equal to 1.",
                field="day_number",
                value=self.day_number,
            )

    @classmethod
    def create(
        cls,
        *,
        day_id: ItineraryDayId,
        itinerary_id: ItineraryId,
        day_number: int,
        title: str | None = None,
        date: date | None = None,
        items: list[ItineraryItem] | None = None,
    ) -> ItineraryDay:
        """Create a new ItineraryDay entity."""
        return cls(
            entity_id=day_id,
            itinerary_id=itinerary_id,
            day_number=day_number,
            title=title,
            date=date,
            items=items or [],
        )
