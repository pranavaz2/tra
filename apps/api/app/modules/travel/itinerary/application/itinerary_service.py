"""Itinerary Application Layer — Itinerary Domain Service."""

from __future__ import annotations

import logging
from uuid import UUID

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.itinerary.application.commands import (
    AddItineraryDayCommand,
    AddItineraryItemCommand,
    CreateItineraryCommand,
    RemoveItineraryDayCommand,
    RemoveItineraryItemCommand,
    UpdateItineraryDayCommand,
    UpdateItineraryItemCommand,
)
from app.modules.travel.itinerary.application.dtos import (
    AddItineraryDayResult,
    AddItineraryItemResult,
    CreateItineraryResult,
    GetItineraryResult,
    ItineraryDaySummary,
    ItineraryItemSummary,
    ItinerarySummary,
    RemoveItineraryDayResult,
    RemoveItineraryItemResult,
    UpdateItineraryDayResult,
    UpdateItineraryItemResult,
)
from app.modules.travel.itinerary.application.queries import GetItineraryQuery
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.errors import (
    ItineraryNotFoundError,
)
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

logger = logging.getLogger(__name__)


class ItineraryService:
    """Application service coordinating Itinerary aggregate operations."""

    def __init__(
        self,
        repository: IItineraryRepository,
        trip_repository: ITripRepository,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
    ) -> None:
        self._repository = repository
        self._trip_repository = trip_repository
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider

    async def get_itinerary(self, query: GetItineraryQuery) -> GetItineraryResult:
        """Fetch the itinerary for a trip, auto-creating an empty one if not found."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        # Try to find existing itinerary
        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            # Auto-create empty itinerary
            try:
                itinerary = await self._auto_create_itinerary(trip_id)
            except TravixError as exc:
                return Failure(exc)

        return Success(self._to_dto(itinerary))

    async def create_itinerary(self, command: CreateItineraryCommand) -> CreateItineraryResult:
        """Explicitly create a new itinerary for a trip."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        # Prevent duplicate itineraries
        existing = await self._repository.find_by_trip_id(trip_id)
        if existing and not existing.is_deleted:
            return Failure(ValidationError("Itinerary already exists for this trip."))

        itinerary_id = ItineraryId(value=self._uuid_provider.generate())
        itinerary = Itinerary.create(itinerary_id=itinerary_id, trip_id=trip_id)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to persist itinerary.", cause=exc))

        await self._publish(itinerary.pop_events(), context="create_itinerary")
        return Success(self._to_dto(itinerary))

    async def add_day(self, command: AddItineraryDayCommand) -> AddItineraryDayResult:
        """Add a day to an itinerary."""
        logger.info(
            "Adding day to itinerary for trip %s, day %s",
            command.trip_id,
            command.day_number,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        # Retrieve or auto-create itinerary
        itinerary = await self._get_or_create_itinerary(trip_id)

        try:
            day_id = ItineraryDayId(value=self._uuid_provider.generate())
            itinerary.add_day(
                day_id=day_id,
                day_number=command.day_number,
                title=command.title,
                date=command.date,
            )
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to add day.", cause=exc))

        await self._publish(itinerary.pop_events(), context="add_day")
        return Success(self._to_dto(itinerary))

    async def update_day(self, command: UpdateItineraryDayCommand) -> UpdateItineraryDayResult:
        """Update an itinerary day's details."""
        logger.info(
            "Updating day %s in itinerary for trip %s",
            command.day_id,
            command.trip_id,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            day_id = ItineraryDayId.from_str(command.day_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            return Failure(ItineraryNotFoundError(str(trip_id)))

        try:
            itinerary.update_day(
                day_id=day_id,
                day_number=command.day_number,
                title=command.title,
                date=command.date,
            )
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to update day.", cause=exc))

        await self._publish(itinerary.pop_events(), context="update_day")
        return Success(self._to_dto(itinerary))

    async def remove_day(self, command: RemoveItineraryDayCommand) -> RemoveItineraryDayResult:
        """Remove a day from an itinerary."""
        logger.info(
            "Removing day %s from itinerary for trip %s",
            command.day_id,
            command.trip_id,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            day_id = ItineraryDayId.from_str(command.day_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            return Failure(ItineraryNotFoundError(str(trip_id)))

        try:
            itinerary.remove_day(day_id)
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to remove day.", cause=exc))

        await self._publish(itinerary.pop_events(), context="remove_day")
        return Success(self._to_dto(itinerary))

    async def add_item(self, command: AddItineraryItemCommand) -> AddItineraryItemResult:
        """Add a scheduled item to an itinerary day."""
        logger.info(
            "Adding item to day %s for trip %s",
            command.day_id,
            command.trip_id,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            day_id = ItineraryDayId.from_str(command.day_id)
            requester_id = UserId.from_str(command.requester_id)
            title = ItemTitle(value=command.title)
            item_type = ItineraryItemType(command.item_type)
            location_id = UUID(command.location_id) if command.location_id else None
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            return Failure(ItineraryNotFoundError(str(trip_id)))

        try:
            item_id = ItineraryItemId(value=self._uuid_provider.generate())
            itinerary.add_item(
                item_id=item_id,
                day_id=day_id,
                title=title,
                item_type=item_type,
                description=command.description,
                start_time=command.start_time,
                end_time=command.end_time,
                location_id=location_id,
                cost=command.cost,
                currency=command.currency,
            )
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to add item.", cause=exc))

        await self._publish(itinerary.pop_events(), context="add_item")
        return Success(self._to_dto(itinerary))

    async def update_item(self, command: UpdateItineraryItemCommand) -> UpdateItineraryItemResult:
        """Update an itinerary item's details."""
        logger.info(
            "Updating item %s in itinerary for trip %s",
            command.item_id,
            command.trip_id,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            item_id = ItineraryItemId.from_str(command.item_id)
            day_id = ItineraryDayId.from_str(command.day_id) if command.day_id else None
            requester_id = UserId.from_str(command.requester_id)
            title = ItemTitle(value=command.title)
            item_type = ItineraryItemType(command.item_type)
            location_id = UUID(command.location_id) if command.location_id else None
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            return Failure(ItineraryNotFoundError(str(trip_id)))

        try:
            itinerary.update_item(
                item_id=item_id,
                day_id=day_id,
                title=title,
                item_type=item_type,
                description=command.description,
                start_time=command.start_time,
                end_time=command.end_time,
                location_id=location_id,
                cost=command.cost,
                currency=command.currency,
            )
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to update item.", cause=exc))

        await self._publish(itinerary.pop_events(), context="update_item")
        return Success(self._to_dto(itinerary))

    async def remove_item(self, command: RemoveItineraryItemCommand) -> RemoveItineraryItemResult:
        """Remove an item from the itinerary."""
        logger.info(
            "Removing item %s from itinerary for trip %s",
            command.item_id,
            command.trip_id,
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            item_id = ItineraryItemId.from_str(command.item_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            await self._check_ownership(trip_id, requester_id)
        except TravixError as exc:
            return Failure(exc)

        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            return Failure(ItineraryNotFoundError(str(trip_id)))

        try:
            itinerary.remove_item(item_id)
        except TravixError as exc:
            return Failure(exc)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to remove item.", cause=exc))

        await self._publish(itinerary.pop_events(), context="remove_item")
        return Success(self._to_dto(itinerary))

    async def _check_ownership(self, trip_id: TripId, requester_id: UserId) -> None:
        """Ensure the trip exists and is owned by the requester."""
        trip = await self._trip_repository.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            raise TripNotFoundError(str(trip_id))

        if trip.owner_id != requester_id:
            raise ForbiddenError("You do not own this trip.")

    async def _get_or_create_itinerary(self, trip_id: TripId) -> Itinerary:
        """Retrieve the itinerary, or create and persist it if not exists."""
        itinerary = await self._repository.find_by_trip_id(trip_id)
        if itinerary is None or itinerary.is_deleted:
            itinerary = await self._auto_create_itinerary(trip_id)
        return itinerary

    async def _auto_create_itinerary(self, trip_id: TripId) -> Itinerary:
        """Helper to create and commit an itinerary implicitly."""
        itinerary_id = ItineraryId(value=self._uuid_provider.generate())
        itinerary = Itinerary.create(itinerary_id=itinerary_id, trip_id=trip_id)

        try:
            async with self._uow:
                await self._repository.save(itinerary)
                await self._uow.commit()
        except Exception as exc:
            logger.error(
                "auto_create_itinerary: persistence failed for trip %s, reason: %s",
                trip_id,
                exc,
            )
            # Fail silently and return transient instance if DB failed,
            # or let it raise depending on severity. Here we raise:
            raise InfrastructureError("Failed to auto-create itinerary.", cause=exc) from exc

        await self._publish(itinerary.pop_events(), context="auto_create_itinerary")
        return itinerary

    def _to_dto(self, itinerary: Itinerary) -> ItinerarySummary:
        """Map an Itinerary aggregate to an ItinerarySummary DTO."""
        days_dto = []
        for day in itinerary.days:
            items_dto = []
            for item in day.items:
                items_dto.append(
                    ItineraryItemSummary(
                        item_id=item.entity_id.value,
                        day_id=item.day_id.value,
                        title=item.title.value,
                        item_type=item.item_type,
                        description=item.description,
                        start_time=item.start_time,
                        end_time=item.end_time,
                        location_id=item.location_id,
                        cost=item.cost,
                        currency=item.currency,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )
            days_dto.append(
                ItineraryDaySummary(
                    day_id=day.entity_id.value,
                    day_number=day.day_number,
                    title=day.title,
                    date=day.date,
                    items=tuple(items_dto),
                    created_at=day.created_at,
                    updated_at=day.updated_at,
                )
            )
        return ItinerarySummary(
            itinerary_id=itinerary.itinerary_id.value,
            trip_id=itinerary.trip_id.value,
            days=tuple(days_dto),
            version=itinerary.version,
            created_at=itinerary.created_at,
            updated_at=itinerary.updated_at,
            deleted_at=itinerary.deleted_at,
        )

    async def _publish(self, events: list[DomainEvent], context: str) -> None:
        """Publish events to the event publisher."""
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Failed to publish events for context %s, reason: %s",
                context,
                exc,
            )
