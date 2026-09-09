"""Unit tests for NotificationPreferences domain entity and service logic."""

from __future__ import annotations

from datetime import time
import uuid

from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory


def test_default_notification_preferences():
    """Verify default preferences enable all standard categories and push."""
    user_id = uuid.uuid4()
    prefs = NotificationPreferences.default_for_user(user_id)

    assert prefs.user_id == user_id
    assert prefs.push_enabled is True
    assert prefs.email_enabled is True
    assert prefs.trip_reminders is True
    assert prefs.itinerary_reminders is True
    assert prefs.collaboration is True
    assert prefs.budget_alerts is True
    assert prefs.travel_warnings is True
    assert prefs.weather_alerts is True

    # All categories should be enabled by default
    for cat in NotificationCategory:
        assert prefs.is_category_enabled(cat) is True


def test_master_push_toggle_disables_all_categories():
    """Verify that disabling push_enabled suppresses all categories."""
    user_id = uuid.uuid4()
    prefs = NotificationPreferences.default_for_user(user_id)
    prefs.push_enabled = False

    for cat in NotificationCategory:
        assert prefs.is_category_enabled(cat) is False


def test_granular_category_toggle():
    """Verify specific category toggles take effect independently."""
    user_id = uuid.uuid4()
    prefs = NotificationPreferences.default_for_user(user_id)

    prefs.update_settings(
        budget_alerts=False,
        weather_alerts=False,
    )

    assert prefs.is_category_enabled(NotificationCategory.BUDGET_ALERTS) is False
    assert prefs.is_category_enabled(NotificationCategory.WEATHER_ALERTS) is False
    assert prefs.is_category_enabled(NotificationCategory.TRIP_REMINDERS) is True
    assert prefs.is_category_enabled(NotificationCategory.COLLABORATION) is True


def test_quiet_hours_evaluation_daytime():
    """Verify quiet hours check for standard daytime interval."""
    user_id = uuid.uuid4()
    prefs = NotificationPreferences.default_for_user(user_id)
    prefs.quiet_hours_start = time(13, 0)
    prefs.quiet_hours_end = time(15, 0)

    assert prefs.is_in_quiet_hours(time(12, 59)) is False
    assert prefs.is_in_quiet_hours(time(13, 0)) is True
    assert prefs.is_in_quiet_hours(time(14, 30)) is True
    assert prefs.is_in_quiet_hours(time(15, 0)) is True
    assert prefs.is_in_quiet_hours(time(15, 1)) is False


def test_quiet_hours_evaluation_over_midnight():
    """Verify quiet hours check across midnight (e.g. 22:00 to 07:00)."""
    user_id = uuid.uuid4()
    prefs = NotificationPreferences.default_for_user(user_id)
    prefs.quiet_hours_start = time(22, 0)
    prefs.quiet_hours_end = time(7, 0)

    assert prefs.is_in_quiet_hours(time(21, 59)) is False
    assert prefs.is_in_quiet_hours(time(22, 0)) is True
    assert prefs.is_in_quiet_hours(time(23, 30)) is True
    assert prefs.is_in_quiet_hours(time(3, 0)) is True
    assert prefs.is_in_quiet_hours(time(7, 0)) is True
    assert prefs.is_in_quiet_hours(time(7, 1)) is False
