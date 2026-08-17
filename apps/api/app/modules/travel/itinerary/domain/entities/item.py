"""ItineraryItem entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from uuid import UUID

from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class ItineraryItem(Entity[ItineraryItemId]):
    """
    ItineraryItem entity inside the Itinerary Aggregate Root boundary.

    Represents a specific scheduled activity or travel segment.
    """

    day_id: ItineraryDayId
    title: ItemTitle
    item_type: ItineraryItemType
    description: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    location_id: UUID | None = None
    cost: Decimal | None = None
    currency: str | None = None

    @classmethod
    def create(
        cls,
        *,
        item_id: ItineraryItemId,
        day_id: ItineraryDayId,
        title: ItemTitle,
        item_type: ItineraryItemType,
        description: str | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        location_id: UUID | None = None,
        cost: Decimal | None = None,
        currency: str | None = None,
    ) -> ItineraryItem:
        """Create a new ItineraryItem entity."""
        return cls(
            entity_id=item_id,
            day_id=day_id,
            title=title,
            item_type=item_type,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location_id=location_id,
            cost=cost,
            currency=currency,
        )
