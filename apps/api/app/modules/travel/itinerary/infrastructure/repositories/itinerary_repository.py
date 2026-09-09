"""SQLAlchemyItineraryRepository — infrastructure implementation of IItineraryRepository."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db.query import exclude_deleted
from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.itinerary.infrastructure.models.itinerary_model import (
    ItineraryDayModel,
    ItineraryItemModel,
    ItineraryModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId

logger = logging.getLogger(__name__)


class SQLAlchemyItineraryRepository:
    """Async SQLAlchemy implementation of IItineraryRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------------------------------------------------------------------- #
    # IItineraryRepository — reads                                             #
    # ---------------------------------------------------------------------- #

    async def find_by_id(self, itinerary_id: ItineraryId) -> Itinerary | None:
        """Return the Itinerary with the given ID, or None."""
        stmt = (
            select(ItineraryModel)
            .where(ItineraryModel.id == itinerary_id.value)
            .options(selectinload(ItineraryModel.days).selectinload(ItineraryDayModel.items))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        """Return the Itinerary for the given Trip, or None."""
        stmt = (
            select(ItineraryModel)
            .where(ItineraryModel.trip_id == trip_id.value)
            .options(selectinload(ItineraryModel.days).selectinload(ItineraryDayModel.items))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def exists(self, itinerary_id: ItineraryId) -> bool:
        """Return True if a non-deleted itinerary with this ID exists."""
        stmt = select(ItineraryModel.id).where(ItineraryModel.id == itinerary_id.value)
        stmt = exclude_deleted(stmt, ItineraryModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Return True if a non-deleted itinerary for this Trip ID exists."""
        stmt = select(ItineraryModel.id).where(ItineraryModel.trip_id == trip_id.value)
        stmt = exclude_deleted(stmt, ItineraryModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    # ---------------------------------------------------------------------- #
    # IItineraryRepository — writes                                            #
    # ---------------------------------------------------------------------- #

    async def save(self, itinerary: Itinerary) -> None:
        """Persist a new or updated itinerary using ORM synchronization."""
        stmt = (
            select(ItineraryModel)
            .where(ItineraryModel.id == itinerary.itinerary_id.value)
            .options(selectinload(ItineraryModel.days).selectinload(ItineraryDayModel.items))
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = ItineraryModel(id=itinerary.itinerary_id.value)
            self._session.add(model)

        # Synchronize attributes
        model.trip_id = itinerary.trip_id.value
        model.deleted_at = itinerary.deleted_at
        model.created_at = itinerary.created_at
        model.updated_at = itinerary.updated_at
        # Do not copy version to avoid interfering with SQLAlchemy's version tracking

        # Synchronize Days
        existing_days = {d.id: d for d in model.days}
        domain_days = {d.entity_id.value: d for d in itinerary.days}

        # 1. Update/Add Days
        updated_days = []
        for d_id, d_domain in domain_days.items():
            if d_id in existing_days:
                d_model = existing_days[d_id]
            else:
                d_model = ItineraryDayModel(id=d_id)
                model.days.append(d_model)

            d_model.day_number = d_domain.day_number
            d_model.title = d_domain.title
            d_model.date = d_domain.date
            d_model.created_at = d_domain.created_at
            d_model.updated_at = d_domain.updated_at
            updated_days.append(d_model)

            # Synchronize Items for this day
            existing_items = {i.id: i for i in d_model.items}
            domain_items = {i.entity_id.value: i for i in d_domain.items}

            # Update/Add Items
            updated_items = []
            for i_id, i_domain in domain_items.items():
                if i_id in existing_items:
                    i_model = existing_items[i_id]
                else:
                    i_model = ItineraryItemModel(id=i_id)
                    d_model.items.append(i_model)

                i_model.title = str(i_domain.title)
                i_model.item_type = i_domain.item_type.value
                i_model.description = i_domain.description
                i_model.start_time = i_domain.start_time
                i_model.end_time = i_domain.end_time
                i_model.location_id = i_domain.location_id
                i_model.cost = i_domain.cost
                i_model.currency = i_domain.currency
                i_model.created_at = i_domain.created_at
                i_model.updated_at = i_domain.updated_at
                updated_items.append(i_model)

            # Delete removed items
            for i_id in list(existing_items.keys()):
                if i_id not in domain_items:
                    # Remove it from collection
                    d_model.items.remove(existing_items[i_id])

        # 2. Delete removed days
        for d_id in list(existing_days.keys()):
            if d_id not in domain_days:
                model.days.remove(existing_days[d_id])

        await self._session.flush([model])

    # ---------------------------------------------------------------------- #
    # Domain Mapping Helpers                                                   #
    # ---------------------------------------------------------------------- #

    def _to_domain(self, model: ItineraryModel) -> Itinerary:
        """Map ItineraryModel to Itinerary domain aggregate."""
        days = []
        for d_model in model.days:
            items = []
            for i_model in d_model.items:
                items.append(
                    ItineraryItem(
                        entity_id=ItineraryItemId(value=i_model.id),
                        day_id=ItineraryDayId(value=i_model.day_id),
                        title=ItemTitle(value=i_model.title),
                        item_type=ItineraryItemType(i_model.item_type),
                        description=i_model.description,
                        start_time=i_model.start_time,
                        end_time=i_model.end_time,
                        location_id=i_model.location_id,
                        cost=i_model.cost,
                        currency=i_model.currency,
                        created_at=i_model.created_at,
                        updated_at=i_model.updated_at,
                    )
                )

            days.append(
                ItineraryDay(
                    entity_id=ItineraryDayId(value=d_model.id),
                    itinerary_id=ItineraryId(value=d_model.itinerary_id),
                    day_number=d_model.day_number,
                    title=d_model.title,
                    date=d_model.date,
                    items=items,
                    created_at=d_model.created_at,
                    updated_at=d_model.updated_at,
                )
            )

        days.sort(key=lambda d: d.day_number)

        return Itinerary(
            entity_id=ItineraryId(value=model.id),
            trip_id=TripId(value=model.trip_id),
            days=days,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )
