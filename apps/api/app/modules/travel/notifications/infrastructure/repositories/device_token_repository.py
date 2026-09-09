"""SQLAlchemy implementation of IDeviceTokenRepository."""

from __future__ import annotations

import uuid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.travel.notifications.domain.entities.device_token import (
    DevicePushToken,
)
from app.modules.travel.notifications.domain.repositories.interfaces import (
    IDeviceTokenRepository,
)
from app.modules.travel.notifications.infrastructure.models.device_token_model import (
    DevicePushTokenModel,
)


class SQLAlchemyDeviceTokenRepository(IDeviceTokenRepository):
    """PostgreSQL / SQLAlchemy implementation for device push tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, token: DevicePushToken) -> None:
        stmt = select(DevicePushTokenModel).where(DevicePushTokenModel.token == token.token)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.user_id = token.user_id
            existing.platform = token.platform
            existing.device_name = token.device_name
            existing.updated_at = token.updated_at
        else:
            model = DevicePushTokenModel(
                id=token.token_id,
                user_id=token.user_id,
                token=token.token,
                platform=token.platform,
                device_name=token.device_name,
                created_at=token.created_at,
                updated_at=token.updated_at,
            )
            self._session.add(model)
        await self._session.flush()

    async def delete_by_token(self, token: str) -> None:
        stmt = delete(DevicePushTokenModel).where(DevicePushTokenModel.token == token)
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[DevicePushToken]:
        stmt = select(DevicePushTokenModel).where(DevicePushTokenModel.user_id == user_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            DevicePushToken(
                token_id=m.id,
                user_id=m.user_id,
                token=m.token,
                platform=m.platform,
                device_name=m.device_name,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    async def list_by_user_ids(
        self, user_ids: list[uuid.UUID]
    ) -> list[DevicePushToken]:
        if not user_ids:
            return []
        stmt = select(DevicePushTokenModel).where(DevicePushTokenModel.user_id.in_(user_ids))
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            DevicePushToken(
                token_id=m.id,
                user_id=m.user_id,
                token=m.token,
                platform=m.platform,
                device_name=m.device_name,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]
