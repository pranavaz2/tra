"""Notifications Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging
from typing import Generic, TypeVar
import uuid

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.notifications.infrastructure.dependencies import (
    CurrentNotificationService,
)
from app.modules.travel.notifications.presentation.schemas import (
    DeviceTokenResponse,
    NotificationPreferencesResponse,
    RegisterDeviceTokenRequest,
    UpdateNotificationPreferencesRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Push Notifications & Preferences"])

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    """Standard API response envelope."""

    model_config = ConfigDict(frozen=True)
    data: T = Field(description="Payload data")


@router.post(
    "/devices",
    response_model=DataEnvelope[DeviceTokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register device push token",
    operation_id="registerDevicePushToken",
)
async def register_device_token(
    body: RegisterDeviceTokenRequest,
    auth: RequireAuthentication,
    service: CurrentNotificationService,
) -> Response:
    trace_id = get_request_id() or ""
    uid = uuid.UUID(auth.user_id) if isinstance(auth.user_id, str) else auth.user_id

    device_token = await service.register_device_token(
        user_id=uid,
        token=body.token,
        platform=body.platform,
        device_name=body.device_name,
    )

    response_data = DeviceTokenResponse(
        token_id=str(device_token.token_id),
        user_id=str(device_token.user_id),
        token=device_token.token,
        platform=device_token.platform,
        device_name=device_token.device_name,
        created_at=device_token.created_at,
    )
    envelope = DataEnvelope(data=response_data)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=envelope.model_dump(mode="json"),
        headers={"X-Request-ID": trace_id},
    )


@router.delete(
    "/devices/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister device push token",
    operation_id="unregisterDevicePushToken",
)
async def unregister_device_token(
    token: str = Path(description="The push token to delete"),
    auth: RequireAuthentication = None,  # type: ignore
    service: CurrentNotificationService = None,  # type: ignore
) -> Response:
    await service.remove_device_token(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/preferences",
    response_model=DataEnvelope[NotificationPreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user notification preferences",
    operation_id="getNotificationPreferences",
)
async def get_notification_preferences(
    auth: RequireAuthentication,
    service: CurrentNotificationService,
) -> Response:
    trace_id = get_request_id() or ""
    uid = uuid.UUID(auth.user_id) if isinstance(auth.user_id, str) else auth.user_id

    prefs = await service.get_preferences(uid)
    response_data = NotificationPreferencesResponse(
        user_id=str(prefs.user_id),
        push_enabled=prefs.push_enabled,
        email_enabled=prefs.email_enabled,
        trip_reminders=prefs.trip_reminders,
        itinerary_reminders=prefs.itinerary_reminders,
        collaboration=prefs.collaboration,
        budget_alerts=prefs.budget_alerts,
        travel_warnings=prefs.travel_warnings,
        weather_alerts=prefs.weather_alerts,
        quiet_hours_start=prefs.quiet_hours_start.strftime("%H:%M") if prefs.quiet_hours_start else None,
        quiet_hours_end=prefs.quiet_hours_end.strftime("%H:%M") if prefs.quiet_hours_end else None,
        updated_at=prefs.updated_at,
    )
    envelope = DataEnvelope(data=response_data)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=envelope.model_dump(mode="json"),
        headers={"X-Request-ID": trace_id},
    )


@router.patch(
    "/preferences",
    response_model=DataEnvelope[NotificationPreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Update user notification preferences",
    operation_id="updateNotificationPreferences",
)
async def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    auth: RequireAuthentication,
    service: CurrentNotificationService,
) -> Response:
    trace_id = get_request_id() or ""
    uid = uuid.UUID(auth.user_id) if isinstance(auth.user_id, str) else auth.user_id

    prefs = await service.update_preferences(
        user_id=uid,
        push_enabled=body.push_enabled,
        email_enabled=body.email_enabled,
        trip_reminders=body.trip_reminders,
        itinerary_reminders=body.itinerary_reminders,
        collaboration=body.collaboration,
        budget_alerts=body.budget_alerts,
        travel_warnings=body.travel_warnings,
        weather_alerts=body.weather_alerts,
        quiet_hours_start=body.quiet_hours_start,
        quiet_hours_end=body.quiet_hours_end,
    )

    response_data = NotificationPreferencesResponse(
        user_id=str(prefs.user_id),
        push_enabled=prefs.push_enabled,
        email_enabled=prefs.email_enabled,
        trip_reminders=prefs.trip_reminders,
        itinerary_reminders=prefs.itinerary_reminders,
        collaboration=prefs.collaboration,
        budget_alerts=prefs.budget_alerts,
        travel_warnings=prefs.travel_warnings,
        weather_alerts=prefs.weather_alerts,
        quiet_hours_start=prefs.quiet_hours_start.strftime("%H:%M") if prefs.quiet_hours_start else None,
        quiet_hours_end=prefs.quiet_hours_end.strftime("%H:%M") if prefs.quiet_hours_end else None,
        updated_at=prefs.updated_at,
    )
    envelope = DataEnvelope(data=response_data)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=envelope.model_dump(mode="json"),
        headers={"X-Request-ID": trace_id},
    )
