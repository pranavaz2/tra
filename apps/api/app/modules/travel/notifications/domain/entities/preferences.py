"""NotificationPreferences domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time
import uuid

from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class NotificationPreferences(Entity[uuid.UUID]):
    """
    User notification preferences entity.
    
    Controls which categories of push/email notifications a user receives
    and defines optional quiet hours.
    """

    user_id: uuid.UUID
    push_enabled: bool = True
    email_enabled: bool = True
    trip_reminders: bool = True
    itinerary_reminders: bool = True
    collaboration: bool = True
    budget_alerts: bool = True
    travel_warnings: bool = True
    weather_alerts: bool = True
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def default_for_user(cls, user_id: uuid.UUID) -> NotificationPreferences:
        """Create default preferences where all standard categories are enabled."""
        return cls(
            entity_id=uuid.uuid4(),
            user_id=user_id,
            push_enabled=True,
            email_enabled=True,
            trip_reminders=True,
            itinerary_reminders=True,
            collaboration=True,
            budget_alerts=True,
            travel_warnings=True,
            weather_alerts=True,
            quiet_hours_start=None,
            quiet_hours_end=None,
            updated_at=datetime.now(UTC),
        )

    def is_category_enabled(self, category: NotificationCategory) -> bool:
        """Check if push delivery is permitted for a specific category."""
        if not self.push_enabled:
            return False

        match category:
            case NotificationCategory.TRIP_REMINDERS:
                return self.trip_reminders
            case NotificationCategory.ITINERARY_REMINDERS:
                return self.itinerary_reminders
            case NotificationCategory.COLLABORATION:
                return self.collaboration
            case NotificationCategory.BUDGET_ALERTS:
                return self.budget_alerts
            case NotificationCategory.TRAVEL_WARNINGS:
                return self.travel_warnings
            case NotificationCategory.WEATHER_ALERTS:
                return self.weather_alerts
            case _:
                return True

    def is_in_quiet_hours(self, current_time: time) -> bool:
        """Check if current time falls within user-configured quiet hours."""
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False

        start = self.quiet_hours_start
        end = self.quiet_hours_end

        if start <= end:
            return start <= current_time <= end
        else:
            # Over midnight (e.g., 22:00 to 07:00)
            return current_time >= start or current_time <= end

    def update_settings(
        self,
        *,
        push_enabled: bool | None = None,
        email_enabled: bool | None = None,
        trip_reminders: bool | None = None,
        itinerary_reminders: bool | None = None,
        collaboration: bool | None = None,
        budget_alerts: bool | None = None,
        travel_warnings: bool | None = None,
        weather_alerts: bool | None = None,
        quiet_hours_start: time | None = None,
        quiet_hours_end: time | None = None,
    ) -> None:
        """Update mutable preference fields."""
        if push_enabled is not None:
            self.push_enabled = push_enabled
        if email_enabled is not None:
            self.email_enabled = email_enabled
        if trip_reminders is not None:
            self.trip_reminders = trip_reminders
        if itinerary_reminders is not None:
            self.itinerary_reminders = itinerary_reminders
        if collaboration is not None:
            self.collaboration = collaboration
        if budget_alerts is not None:
            self.budget_alerts = budget_alerts
        if travel_warnings is not None:
            self.travel_warnings = travel_warnings
        if weather_alerts is not None:
            self.weather_alerts = weather_alerts
        if quiet_hours_start is not None:
            self.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
            self.quiet_hours_end = quiet_hours_end

        self.updated_at = datetime.now(UTC)
