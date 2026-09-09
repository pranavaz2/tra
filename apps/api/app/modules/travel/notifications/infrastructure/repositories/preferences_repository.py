"""SQLAlchemy implementation of INotificationPreferencesRepository."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.domain.repositories.interfaces import (
    INotificationPreferencesRepository,
)
from app.modules.travel.notifications.infrastructure.models.preferences_model import (
    NotificationPreferencesModel,
)


class SQLAlchemyNotificationPreferencesRepository(INotificationPreferencesRepository):
    """PostgreSQL / SQLAlchemy implementation of notification preferences repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> NotificationPreferences | None:
        stmt = select(NotificationPreferencesModel).where(
            NotificationPreferencesModel.user_id == user_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def save(self, preferences: NotificationPreferences) -> None:
        stmt = select(NotificationPreferencesModel).where(
            NotificationPreferencesModel.user_id == preferences.user_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.push_enabled = preferences.push_enabled
            model.email_enabled = preferences.email_enabled
            model.trip_reminders = preferences.trip_reminders
            model.itinerary_reminders = preferences.itinerary_reminders
            model.collaboration = preferences.collaboration
            model.budget_alerts = preferences.budget_alerts
            model.travel_warnings = preferences.travel_warnings
            model.weather_alerts = preferences.weather_alerts
            model.quiet_hours_start = preferences.quiet_hours_start
            model.quiet_hours_end = preferences.quiet_hours_end
            model.updated_at = preferences.updated_at
        else:
            model = NotificationPreferencesModel(
                preference_id=preferences.entity_id,
                user_id=preferences.user_id,
                push_enabled=preferences.push_enabled,
                email_enabled=preferences.email_enabled,
                trip_reminders=preferences.trip_reminders,
                itinerary_reminders=preferences.itinerary_reminders,
                collaboration=preferences.collaboration,
                budget_alerts=preferences.budget_alerts,
                travel_warnings=preferences.travel_warnings,
                weather_alerts=preferences.weather_alerts,
                quiet_hours_start=preferences.quiet_hours_start,
                quiet_hours_end=preferences.quiet_hours_end,
                updated_at=preferences.updated_at,
            )
            self._session.add(model)
        await self._session.flush()

    def _to_domain(self, model: NotificationPreferencesModel) -> NotificationPreferences:
        return NotificationPreferences(
            entity_id=model.preference_id,
            user_id=model.user_id,
            push_enabled=model.push_enabled,
            email_enabled=model.email_enabled,
            trip_reminders=model.trip_reminders,
            itinerary_reminders=model.itinerary_reminders,
            collaboration=model.collaboration,
            budget_alerts=model.budget_alerts,
            travel_warnings=model.travel_warnings,
            weather_alerts=model.weather_alerts,
            quiet_hours_start=model.quiet_hours_start,
            quiet_hours_end=model.quiet_hours_end,
            updated_at=model.updated_at,
        )
