"""SQLAlchemy-backed repository for UserPreferences."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences
from app.modules.travel.recommendations.domain.enums.budget_tier import BudgetTier
from app.modules.travel.recommendations.domain.enums.travel_pace import TravelPace
from app.modules.travel.recommendations.domain.enums.travel_style import TravelStyle
from app.modules.travel.recommendations.domain.repositories.interfaces import (
    IUserPreferencesRepository,
)
from app.modules.travel.recommendations.domain.value_objects.dietary_tag import DietaryTag
from app.modules.travel.recommendations.domain.value_objects.interest_tag import InterestTag
from app.modules.travel.recommendations.domain.value_objects.preferences_id import PreferencesId
from app.modules.travel.recommendations.infrastructure.models.preferences_model import (
    UserPreferencesModel,
)


class SQLAlchemyUserPreferencesRepository(IUserPreferencesRepository):
    """SQLAlchemy implementation of IUserPreferencesRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user_id(self, user_id: UserId) -> UserPreferences | None:
        """Find UserPreferences by UserId."""
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def save(self, preferences: UserPreferences) -> None:
        """Save UserPreferences in database."""
        stmt = select(UserPreferencesModel).where(
            UserPreferencesModel.id == preferences.entity_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is not None:
            # Optimistic concurrency check
            if model.version != preferences.version:
                raise ValueError("Concurrency collision on UserPreferences.")

            model.interests = [tag.value for tag in preferences.interests]
            model.dietary_preferences = [tag.value for tag in preferences.dietary_preferences]
            model.travel_style = preferences.travel_style.value
            model.travel_pace = preferences.travel_pace.value
            model.budget_tier = preferences.budget_tier.value
            model.version += 1
            model.updated_at = preferences.updated_at
            # Sync domain version with incremented DB version
            object.__setattr__(preferences, "version", model.version)
        else:
            model = UserPreferencesModel(
                id=preferences.entity_id.value,
                user_id=preferences.user_id.value,
                interests=[tag.value for tag in preferences.interests],
                dietary_preferences=[tag.value for tag in preferences.dietary_preferences],
                travel_style=preferences.travel_style.value,
                travel_pace=preferences.travel_pace.value,
                budget_tier=preferences.budget_tier.value,
                version=preferences.version,
                created_at=preferences.created_at,
                updated_at=preferences.updated_at,
            )
            self._session.add(model)

    def _to_domain(self, model: UserPreferencesModel) -> UserPreferences:
        """Map ORM model to domain aggregate root."""
        return UserPreferences(
            entity_id=PreferencesId(value=model.id),
            user_id=UserId(value=model.user_id),
            interests=[InterestTag(value=t) for t in model.interests],
            dietary_preferences=[DietaryTag(value=t) for t in model.dietary_preferences],
            travel_style=TravelStyle(model.travel_style),
            travel_pace=TravelPace(model.travel_pace),
            budget_tier=BudgetTier(model.budget_tier),
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
