"""SQLAlchemy implementation of ITripActivityRepository."""

from __future__ import annotations

import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.travel.activity.domain.entities.activity_log import TripActivityLog
from app.modules.travel.activity.domain.enums import ActivityAction
from app.modules.travel.activity.domain.repositories.interfaces import (
    ITripActivityRepository,
)
from app.modules.travel.activity.infrastructure.models.activity_model import (
    TripActivityModel,
)


class SQLAlchemyTripActivityRepository(ITripActivityRepository):
    """PostgreSQL / SQLAlchemy repository for trip activity logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, activity: TripActivityLog) -> None:
        model = TripActivityModel(
            id=activity.activity_id,
            trip_id=activity.trip_id,
            actor_id=activity.actor_id,
            action=activity.action.value,
            entity_type=activity.entity_type,
            entity_id=activity.entity_id,
            title=activity.title,
            description=activity.description,
            metadata_json=activity.metadata,
            created_at=activity.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def list_by_trip(
        self,
        trip_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TripActivityLog]:
        stmt = (
            select(TripActivityModel)
            .where(TripActivityModel.trip_id == trip_id)
            .order_by(TripActivityModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            TripActivityLog(
                activity_id=m.id,
                trip_id=m.trip_id,
                actor_id=m.actor_id,
                action=ActivityAction(m.action),
                entity_type=m.entity_type,
                entity_id=m.entity_id,
                title=m.title,
                description=m.description,
                metadata=m.metadata_json or {},
                created_at=m.created_at,
            )
            for m in models
        ]

    async def count_by_trip(self, trip_id: uuid.UUID) -> int:
        stmt = (
            select(func.count(TripActivityModel.id))
            .where(TripActivityModel.trip_id == trip_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0
