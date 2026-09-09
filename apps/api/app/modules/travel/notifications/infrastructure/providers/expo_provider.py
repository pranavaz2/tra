"""Expo Push Notification HTTP Provider."""

from __future__ import annotations

import logging
from typing import Any
import httpx

from app.modules.travel.notifications.domain.provider import (
    IPushNotificationProvider,
    PushMessage,
    PushTicket,
)

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class ExpoPushNotificationProvider(IPushNotificationProvider):
    """Sends push messages via Expo's HTTP push service."""

    def __init__(self, timeout: float = 8.0) -> None:
        self._timeout = timeout

    async def send_messages(
        self,
        messages: list[PushMessage],
    ) -> list[PushTicket]:
        if not messages:
            return []

        payload = [
            {
                "to": msg.to,
                "title": msg.title,
                "body": msg.body,
                "data": msg.data,
                "sound": msg.sound,
                "priority": msg.priority,
                **({"badge": msg.badge} if msg.badge is not None else {}),
            }
            for msg in messages
        ]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/json",
                    },
                )
                if response.status_code != 200:
                    logger.warning(
                        "Expo push service returned status %s: %s",
                        response.status_code,
                        response.text,
                    )
                    return [
                        PushTicket(
                            status="error",
                            message=f"HTTP status {response.status_code}",
                        )
                        for _ in messages
                    ]

                data = response.json()
                tickets_data = data.get("data", [])
                return [
                    PushTicket(
                        status=t.get("status", "ok"),
                        id=t.get("id"),
                        message=t.get("message"),
                        details=t.get("details", {}),
                    )
                    for t in tickets_data
                ]

        except Exception as exc:
            logger.warning("Failed to send push notifications to Expo: %s", exc)
            return [
                PushTicket(status="error", message=str(exc))
                for _ in messages
            ]


class MockPushNotificationProvider(IPushNotificationProvider):
    """In-memory push notification provider for unit/integration testing."""

    def __init__(self) -> None:
        self.sent_messages: list[PushMessage] = []

    async def send_messages(
        self,
        messages: list[PushMessage],
    ) -> list[PushTicket]:
        self.sent_messages.extend(messages)
        return [
            PushTicket(status="ok", id=f"ticket-{i}")
            for i, _ in enumerate(messages)
        ]
