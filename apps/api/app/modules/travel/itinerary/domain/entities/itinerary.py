"""Itinerary aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.errors import (
    ItineraryAlreadyDeletedError,
    ItineraryDayAlreadyExistsError,
    ItineraryDayNotFoundError,
    ItineraryItemNotFoundError,
)
from app.modules.travel.itinerary.domain.events.itinerary_events import (
    ItineraryCreated,
    ItineraryDayAdded,
    ItineraryDayRemoved,
    ItineraryDayUpdated,
    ItineraryDeleted,
    ItineraryItemAdded,
    ItineraryItemRemoved,
    ItineraryItemUpdated,
)
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot


@dataclass(kw_only=True, eq=False)
class Itinerary(AggregateRoot[ItineraryId]):
    """
    Itinerary aggregate root.

    Manages a day-by-day travel plan containing multiple days and activities/segments.
    """

    trip_id: TripId
    days: list[ItineraryDay] = field(default_factory=list)
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        itinerary_id: ItineraryId,
        trip_id: TripId,
    ) -> Itinerary:
        """Create a new empty Itinerary aggregate."""
        itinerary = cls(
            entity_id=itinerary_id,
            trip_id=trip_id,
            days=[],
            version=1,
        )
        itinerary.push_event(
            ItineraryCreated(
                aggregate_id=str(itinerary_id),
                itinerary_id=str(itinerary_id),
                trip_id=str(trip_id),
            )
        )
        return itinerary

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def itinerary_id(self) -> ItineraryId:
        """Alias for entity_id with the concrete ItineraryId type."""
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_deleted(self) -> bool:
        """True if this itinerary has been soft-deleted."""
        return self.deleted_at is not None

    # ------------------------------------------------------------------ #
    # Mutators                                                             #
    # ------------------------------------------------------------------ #

    def add_day(
        self,
        *,
        day_id: ItineraryDayId,
        day_number: int,
        title: str | None = None,
        date: date | None = None,
    ) -> ItineraryDay:
        """Add a new day to the itinerary."""
        self._guard_not_deleted()

        # Check if day number already exists
        if any(d.day_number == day_number for d in self.days):
            raise ItineraryDayAlreadyExistsError(day_number)

        day = ItineraryDay.create(
            day_id=day_id,
            itinerary_id=self.itinerary_id,
            day_number=day_number,
            title=title,
            date=date,
        )
        self.days.append(day)
        self.days.sort(key=lambda d: d.day_number)

        self._mutate()
        self.push_event(
            ItineraryDayAdded(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day_id),
                day_number=day_number,
                title=title,
                date=date,
            )
        )
        return day

    def update_day(
        self,
        *,
        day_id: ItineraryDayId,
        day_number: int,
        title: str | None = None,
        date: date | None = None,
    ) -> None:
        """Update an existing day's details."""
        self._guard_not_deleted()

        day = self._find_day(day_id)

        # Check if the new day number is taken by another day
        if day.day_number != day_number and any(d.day_number == day_number for d in self.days):
            raise ItineraryDayAlreadyExistsError(day_number)

        day.day_number = day_number
        day.title = title
        day.date = date
        day.touch()

        self.days.sort(key=lambda d: d.day_number)

        self._mutate()
        self.push_event(
            ItineraryDayUpdated(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day_id),
                day_number=day_number,
                title=title,
                date=date,
            )
        )

    def remove_day(self, day_id: ItineraryDayId) -> None:
        """Remove a day and all its items from the itinerary."""
        self._guard_not_deleted()

        day = self._find_day(day_id)
        self.days.remove(day)

        self._mutate()
        self.push_event(
            ItineraryDayRemoved(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day_id),
            )
        )

    def add_item(
        self,
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
        """Add a scheduled item to a specific day."""
        self._guard_not_deleted()

        day = self._find_day(day_id)
        item = ItineraryItem.create(
            item_id=item_id,
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
        day.items.append(item)
        day.touch()

        self._mutate()
        self.push_event(
            ItineraryItemAdded(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day_id),
                item_id=str(item_id),
                title=str(title),
                item_type=item_type.value,
            )
        )
        return item

    def update_item(
        self,
        *,
        item_id: ItineraryItemId,
        day_id: ItineraryDayId | None = None,
        title: ItemTitle,
        item_type: ItineraryItemType,
        description: str | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        location_id: UUID | None = None,
        cost: Decimal | None = None,
        currency: str | None = None,
    ) -> None:
        """Update an existing item's details."""
        self._guard_not_deleted()

        old_day, item = self._find_item(item_id)

        # Handle moving the item to a different day
        if day_id is not None and old_day.entity_id != day_id:
            new_day = self._find_day(day_id)
            old_day.items.remove(item)
            old_day.touch()
            new_day.items.append(item)
            new_day.touch()
            item.day_id = day_id
        else:
            day_id = old_day.entity_id

        item.title = title
        item.item_type = item_type
        item.description = description
        item.start_time = start_time
        item.end_time = end_time
        item.location_id = location_id
        item.cost = cost
        item.currency = currency
        item.touch()

        self._mutate()
        self.push_event(
            ItineraryItemUpdated(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day_id),
                item_id=str(item_id),
                title=str(title),
                item_type=item_type.value,
            )
        )

    def remove_item(self, item_id: ItineraryItemId) -> None:
        """Remove a scheduled item from the itinerary."""
        self._guard_not_deleted()

        day, item = self._find_item(item_id)
        day.items.remove(item)
        day.touch()

        self._mutate()
        self.push_event(
            ItineraryItemRemoved(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                day_id=str(day.entity_id),
                item_id=str(item_id),
            )
        )

    def delete(self) -> None:
        """Soft-delete this itinerary."""
        self._guard_not_deleted()
        self.deleted_at = datetime.now(UTC)
        self._mutate()
        self.push_event(
            ItineraryDeleted(
                aggregate_id=str(self.itinerary_id),
                itinerary_id=str(self.itinerary_id),
                trip_id=str(self.trip_id),
            )
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _guard_not_deleted(self) -> None:
        if self.is_deleted:
            raise ItineraryAlreadyDeletedError()

    def _mutate(self) -> None:
        """Increment the version counter and refresh updated_at."""
        self.version += 1
        self.touch()

    def _find_day(self, day_id: ItineraryDayId) -> ItineraryDay:
        for day in self.days:
            if day.entity_id == day_id:
                return day
        raise ItineraryDayNotFoundError(str(day_id))

    def _find_item(self, item_id: ItineraryItemId) -> tuple[ItineraryDay, ItineraryItem]:
        for day in self.days:
            for item in day.items:
                if item.entity_id == item_id:
                    return day, item
        raise ItineraryItemNotFoundError(str(item_id))
