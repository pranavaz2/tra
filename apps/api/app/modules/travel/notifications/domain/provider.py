"""Push notification provider protocol and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PushMessage:
    """Push notification message payload."""

    to: str  # Push token
    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    sound: str = "default"
    badge: int | None = None
    priority: str = "high"


@dataclass(frozen=True)
class PushTicket:
    """Receipt or ticket returned by the push provider."""

    status: str  # "ok" or "error"
    id: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class IPushNotificationProvider(Protocol):
    """Abstract port for sending push notifications."""

    async def send_messages(
        self,
        messages: list[PushMessage],
    ) -> list[PushTicket]:
        """Deliver a batch of push messages to devices."""
        ...
