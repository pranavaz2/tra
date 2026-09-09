"""SQLAlchemy implementation of ISentNotificationRepository."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.travel.notifications.domain.entities.sent_notification import (
    SentNotificationLog,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.modules.travel.notifications.domain.repositories.interfaces import (
    ISentNotificationRepository,
)
from app.modules.travel.notifications.infrastructure.models.sent_notification_model import (
    SentNotificationModel,
)


class SQLAlchemySentNotificationRepository(ISentNotificationRepository):
    """PostgreSQL / SQLAlchemy implementation of sent notification log repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists_by_dedup_key(self, dedup_key: str) -> bool:
        stmt = select(SentNotificationModel.id).where(
            SentNotificationModel.dedup_key == dedup_key
        ).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def save(self, log: SentNotificationLog) -> None:
        model = SentNotificationModel(
            id=log.entity_id,
            user_id=log.user_id,
            dedup_key=log.dedup_key,
            category=log.category.value,
            trip_id=log.trip_id,
            title=log.title,
            body=log.body,
            payload_json=log.payload,
            sent_at=log.sent_at,
        )
        self._session.add(model)
        await self._session.flush()
