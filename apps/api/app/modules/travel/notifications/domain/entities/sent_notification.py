"""SentNotificationLog domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class SentNotificationLog(Entity[uuid.UUID]):
    """
    Immutable record of a dispatched notification.
    
    Persisted to prevent duplicate sends across server restarts.
    """

    user_id: uuid.UUID
    dedup_key: str
    category: NotificationCategory
    trip_id: uuid.UUID | None = None
    title: str
    body: str
    payload: dict[str, Any] = field(default_factory=dict)
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        dedup_key: str,
        category: NotificationCategory,
        title: str,
        body: str,
        trip_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SentNotificationLog:
        return cls(
            entity_id=uuid.uuid4(),
            user_id=user_id,
            dedup_key=dedup_key,
            category=category,
            title=title,
            body=body,
            trip_id=trip_id,
            payload=payload or {},
            sent_at=datetime.now(UTC),
        )
