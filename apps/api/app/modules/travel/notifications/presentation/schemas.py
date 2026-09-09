"""Push notification and preferences presentation schemas."""

from __future__ import annotations

from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field


class RegisterDeviceTokenRequest(BaseModel):
    """Payload to register a device push token."""

    model_config = ConfigDict(frozen=True)

    token: str = Field(min_length=10, max_length=512, description="Expo push token or device APNs/FCM token")
    platform: str = Field(default="expo", description="Target platform (expo, ios, android, web)")
    device_name: str | None = Field(default=None, max_length=128, description="Human readable device name")


class DeviceTokenResponse(BaseModel):
    """Device push token response."""

    model_config = ConfigDict(frozen=True)

    token_id: str
    user_id: str
    token: str
    platform: str
    device_name: str | None
    created_at: datetime


class NotificationPreferencesResponse(BaseModel):
    """User notification preferences response."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    push_enabled: bool
    email_enabled: bool
    trip_reminders: bool
    itinerary_reminders: bool
    collaboration: bool
    budget_alerts: bool
    travel_warnings: bool
    weather_alerts: bool
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    updated_at: datetime


class UpdateNotificationPreferencesRequest(BaseModel):
    """Payload to update user notification preferences."""

    model_config = ConfigDict(frozen=True)

    push_enabled: bool | None = None
    email_enabled: bool | None = None
    trip_reminders: bool | None = None
    itinerary_reminders: bool | None = None
    collaboration: bool | None = None
    budget_alerts: bool | None = None
    travel_warnings: bool | None = None
    weather_alerts: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
