"""Notification domain enums."""

from __future__ import annotations

import enum


class NotificationCategory(str, enum.Enum):
    """Categories for user notification preferences."""

    TRIP_REMINDERS = "trip_reminders"
    ITINERARY_REMINDERS = "itinerary_reminders"
    COLLABORATION = "collaboration"
    BUDGET_ALERTS = "budget_alerts"
    TRAVEL_WARNINGS = "travel_warnings"
    WEATHER_ALERTS = "weather_alerts"


class NotificationPlatform(str, enum.Enum):
    """Supported push notification platforms."""

    EXPO = "expo"
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
