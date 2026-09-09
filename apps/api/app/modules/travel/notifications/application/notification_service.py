"""Push Notification application service with preferences and persisted deduplication."""

from __future__ import annotations

from datetime import UTC, datetime, time
import logging
from typing import Any
import uuid

from app.modules.travel.notifications.domain.entities.device_token import (
    DevicePushToken,
)
from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.domain.entities.sent_notification import (
    SentNotificationLog,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.modules.travel.notifications.domain.provider import (
    IPushNotificationProvider,
    PushMessage,
)
from app.modules.travel.notifications.domain.repositories.interfaces import (
    IDeviceTokenRepository,
    INotificationPreferencesRepository,
    ISentNotificationRepository,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates device token management, preferences, and persistent push dispatch."""

    def __init__(
        self,
        *,
        token_repository: IDeviceTokenRepository,
        provider: IPushNotificationProvider,
        preferences_repository: INotificationPreferencesRepository | None = None,
        sent_notification_repository: ISentNotificationRepository | None = None,
    ) -> None:
        self._token_repo = token_repository
        self._provider = provider
        self._prefs_repo = preferences_repository
        self._sent_repo = sent_notification_repository
        # In-memory fast cache for recent event keys
        self._sent_event_notifications: set[str] = set()

    async def register_device_token(
        self,
        *,
        user_id: uuid.UUID,
        token: str,
        platform: str = "expo",
        device_name: str | None = None,
    ) -> DevicePushToken:
        """Register or refresh an active device push token."""
        device_token = DevicePushToken.create(
            user_id=user_id,
            token=token,
            platform=platform,
            device_name=device_name,
        )
        await self._token_repo.save(device_token)
        logger.info("Push token registered [user=%s, platform=%s]", user_id, platform)
        return device_token

    async def remove_device_token(self, token: str) -> None:
        """Unregister a push token (e.g. on user logout)."""
        await self._token_repo.delete_by_token(token)
        logger.info("Push token unregistered [token=%s...]", token[:10] if token else "")

    async def get_preferences(self, user_id: uuid.UUID) -> NotificationPreferences:
        """Get or initialize user notification preferences."""
        if self._prefs_repo:
            prefs = await self._prefs_repo.get_by_user_id(user_id)
            if prefs:
                return prefs
        return NotificationPreferences.default_for_user(user_id)

    async def update_preferences(
        self,
        user_id: uuid.UUID,
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
    ) -> NotificationPreferences:
        """Update and persist user notification preferences."""
        prefs = await self.get_preferences(user_id)
        prefs.update_settings(
            push_enabled=push_enabled,
            email_enabled=email_enabled,
            trip_reminders=trip_reminders,
            itinerary_reminders=itinerary_reminders,
            collaboration=collaboration,
            budget_alerts=budget_alerts,
            travel_warnings=travel_warnings,
            weather_alerts=weather_alerts,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
        )
        if self._prefs_repo:
            await self._prefs_repo.save(prefs)
        logger.info("Updated notification preferences for user %s", user_id)
        return prefs

    async def send_categorized_notification(
        self,
        *,
        user_id: uuid.UUID,
        category: NotificationCategory,
        dedup_key: str,
        title: str,
        body: str,
        trip_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send a notification respecting user preferences, quiet hours, and persistent deduplication.

        Returns True if dispatched to at least one active device token.
        """
        # 1. Check in-memory and persistent DB deduplication
        if dedup_key in self._sent_event_notifications:
            logger.debug("Skipping in-memory duplicate notification: %s", dedup_key)
            return False

        if self._sent_repo:
            already_sent = await self._sent_repo.exists_by_dedup_key(dedup_key)
            if already_sent:
                logger.debug("Skipping persistent duplicate notification: %s", dedup_key)
                self._sent_event_notifications.add(dedup_key)
                return False

        # 2. Check User Preferences
        prefs = await self.get_preferences(user_id)
        if not prefs.is_category_enabled(category):
            logger.info("Notification category '%s' muted by user %s", category.value, user_id)
            return False

        # 3. Check Quiet Hours
        current_utc_time = datetime.now(UTC).time()
        if prefs.is_in_quiet_hours(current_utc_time):
            logger.info("Notification suppressed during quiet hours for user %s", user_id)
            return False

        # 4. Fetch Active Device Tokens
        try:
            tokens = await self._token_repo.list_by_user_id(user_id)
            if not tokens:
                logger.debug("No active push tokens found for user %s", user_id)
                # Still record in sent log so we don't spam when token registers later
                await self._record_sent_log(user_id, dedup_key, category, title, body, trip_id, payload)
                return False

            messages = [
                PushMessage(
                    to=t.token,
                    title=title,
                    body=body,
                    data=payload or {},
                )
                for t in tokens
            ]

            await self._provider.send_messages(messages)
            logger.info("Dispatched %d push messages to user %s [%s]", len(messages), user_id, category.value)

            # 5. Persist Sent Record & Update Memory Cache
            await self._record_sent_log(user_id, dedup_key, category, title, body, trip_id, payload)
            self._sent_event_notifications.add(dedup_key)
            return True

        except Exception as exc:
            logger.warning("Error dispatching categorized push notification: %s", exc)
            return False

    async def _record_sent_log(
        self,
        user_id: uuid.UUID,
        dedup_key: str,
        category: NotificationCategory,
        title: str,
        body: str,
        trip_id: uuid.UUID | None,
        payload: dict[str, Any] | None,
    ) -> None:
        if self._sent_repo:
            log_entry = SentNotificationLog.create(
                user_id=user_id,
                dedup_key=dedup_key,
                category=category,
                title=title,
                body=body,
                trip_id=trip_id,
                payload=payload,
            )
            await self._sent_repo.save(log_entry)

    async def notify_users(
        self,
        *,
        event_id: str | None,
        recipient_user_ids: list[uuid.UUID],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        actor_id: uuid.UUID | None = None,
        category: NotificationCategory = NotificationCategory.COLLABORATION,
    ) -> int:
        """Send push notifications to multiple recipients with preference filtering."""
        if not recipient_user_ids:
            return 0

        targets = [uid for uid in recipient_user_ids if uid != actor_id]
        if not targets:
            return 0

        dispatched = 0
        for uid in targets:
            dedup = f"{event_id}:{uid}" if event_id else f"{uuid.uuid4()}:{uid}"
            success = await self.send_categorized_notification(
                user_id=uid,
                category=category,
                dedup_key=dedup,
                title=title,
                body=body,
                payload=data,
            )
            if success:
                dispatched += 1

        return dispatched
