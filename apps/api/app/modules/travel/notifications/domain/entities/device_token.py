"""DevicePushToken domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid


@dataclass(kw_only=True, eq=False)
class DevicePushToken:
    """Represents a registered push notification token for a user device."""

    token_id: uuid.UUID
    user_id: uuid.UUID
    token: str
    platform: str = "expo"  # expo, ios, android, web
    device_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        token: str,
        platform: str = "expo",
        device_name: str | None = None,
        token_id: uuid.UUID | None = None,
    ) -> DevicePushToken:
        now = datetime.now(UTC)
        return cls(
            token_id=token_id or uuid.uuid4(),
            user_id=user_id,
            token=token,
            platform=platform,
            device_name=device_name,
            created_at=now,
            updated_at=now,
        )
