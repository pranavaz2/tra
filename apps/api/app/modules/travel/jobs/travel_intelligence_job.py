"""Scheduled Travel Intelligence background job."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import logging
from typing import Any
import uuid
from zoneinfo import ZoneInfo

from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
)
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.weather.domain.provider import IWeatherProvider

logger = logging.getLogger(__name__)


class ScheduledTravelIntelligenceJob:
    """
    Orchestrates periodic background travel intelligence checks.
    
    Responsibilities:
    - Timezone-aware departure countdown reminders (7d, 24h).
    - Upcoming itinerary activity reminders (~2 hours before start).
    - Severe weather forecasts for planned travel dates.
    - Proactive travel conflict & travel-time feasibility warnings.
    - Strict non-mutation guarantee: never modifies trip, itinerary, or budget entities.
    """

    def __init__(
        self,
        trip_repository: ITripRepository,
        itinerary_repository: IItineraryRepository,
        budget_repository: ITripBudgetRepository,
        sharing_repository: ITripCollaborationRepository,
        notification_service: NotificationService,
        weather_provider: IWeatherProvider,
        proactive_intelligence: ProactiveIntelligenceService | None = None,
    ) -> None:
        self._trip_repo = trip_repository
        self._itinerary_repo = itinerary_repository
        self._budget_repo = budget_repository
        self._sharing_repo = sharing_repository
        self._notification_service = notification_service
        self._weather_provider = weather_provider
        self._proactive_intelligence = proactive_intelligence

    async def execute(self) -> dict[str, int]:
        """Run all scheduled intelligence checks across active trips."""
        logger.info("Executing ScheduledTravelIntelligenceJob")
        stats = {
            "trips_evaluated": 0,
            "trip_reminders_sent": 0,
            "activity_reminders_sent": 0,
            "weather_alerts_sent": 0,
            "travel_warnings_sent": 0,
        }

        # Note: In production, paginate over upcoming/active trips
        trips = await self._trip_repo.list_active_upcoming() if hasattr(self._trip_repo, "list_active_upcoming") else []
        if not trips and hasattr(self._trip_repo, "list_all"):
            trips = await self._trip_repo.list_all()

        for trip in trips:
            stats["trips_evaluated"] += 1
            try:
                # 1. Trip Departure Countdown Reminders
                sent_dep = await self._check_departure_reminders(trip)
                stats["trip_reminders_sent"] += sent_dep

                # 2. Itinerary & Activity Reminders + Weather Alerts
                sent_act, sent_wtr = await self._check_itinerary_and_weather(trip)
                stats["activity_reminders_sent"] += sent_act
                stats["weather_alerts_sent"] += sent_wtr

                # 3. Proactive Travel-Time & Conflict Intelligence
                sent_wrn = await self._check_proactive_warnings(trip)
                stats["travel_warnings_sent"] += sent_wrn

            except Exception as exc:
                logger.error("Error processing scheduled intelligence for trip %s: %s", trip.entity_id, exc)

        logger.info("ScheduledTravelIntelligenceJob complete: %s", stats)
        return stats

    async def _get_trip_recipients(self, trip: Trip) -> list[uuid.UUID]:
        """Collect all collaborator user IDs including owner."""
        recipients = [trip.owner_id.value if hasattr(trip.owner_id, "value") else trip.owner_id]
        collab = await self._sharing_repo.find_by_trip_id(trip.entity_id)
        if collab:
            for member in collab.members:
                mid = member.user_id.value if hasattr(member.user_id, "value") else member.user_id
                if mid not in recipients:
                    recipients.append(mid)
        return recipients

    def _resolve_trip_timezone(self, trip: Trip) -> ZoneInfo:
        """Resolve trip timezone or fallback safely to UTC."""
        tz_str = getattr(trip, "timezone", None)
        if tz_str:
            try:
                return ZoneInfo(tz_str)
            except Exception:
                pass
        return ZoneInfo("UTC")

    async def _check_departure_reminders(self, trip: Trip) -> int:
        """Check for 7-day and 24-hour departure notifications."""
        date_range = getattr(trip, "date_range", None)
        if not date_range or not getattr(date_range, "departure_date", None):
            return 0

        dep_date = date_range.departure_date
        tz = self._resolve_trip_timezone(trip)
        now = datetime.now(tz)
        today = now.date()

        days_until = (dep_date - today).days
        recipients = await self._get_trip_recipients(trip)
        sent_count = 0

        # 7-day reminder
        if days_until == 7:
            for uid in recipients:
                dedup = f"reminder:trip:{trip.entity_id}:7d:{dep_date}:{uid}"
                dispatched = await self._notification_service.send_categorized_notification(
                    user_id=uid,
                    category=NotificationCategory.TRIP_REMINDERS,
                    dedup_key=dedup,
                    trip_id=trip.entity_id.value if hasattr(trip.entity_id, "value") else trip.entity_id,
                    title=f"1 Week Until {trip.title}!",
                    body=f"Your trip begins on {dep_date.strftime('%A, %b %d')}. Time to review packing and plans!",
                    payload={"type": "trip_reminder", "trip_id": str(trip.entity_id), "days_until": 7},
                )
                if dispatched:
                    sent_count += 1

        # 24-hour reminder
        elif days_until == 1:
            for uid in recipients:
                dedup = f"reminder:trip:{trip.entity_id}:24h:{dep_date}:{uid}"
                dispatched = await self._notification_service.send_categorized_notification(
                    user_id=uid,
                    category=NotificationCategory.TRIP_REMINDERS,
                    dedup_key=dedup,
                    trip_id=trip.entity_id.value if hasattr(trip.entity_id, "value") else trip.entity_id,
                    title=f"Tomorrow: {trip.title} Begins!",
                    body="Check in for flights, review your Day 1 itinerary, and have a safe journey.",
                    payload={"type": "trip_reminder", "trip_id": str(trip.entity_id), "days_until": 1},
                )
                if dispatched:
                    sent_count += 1

        return sent_count

    async def _check_itinerary_and_weather(self, trip: Trip) -> tuple[int, int]:
        """Check for 2-hour activity reminders and severe weather warnings."""
        itinerary = await self._itinerary_repo.find_by_trip_id(trip.entity_id)
        if not itinerary or not itinerary.days:
            return 0, 0

        tz = self._resolve_trip_timezone(trip)
        now_dt = datetime.now(tz)
        today = now_dt.date()
        recipients = await self._get_trip_recipients(trip)

        act_sent = 0
        wtr_sent = 0

        for day in itinerary.days:
            if not day.date:
                continue

            # Check weather for upcoming/current days (today and next 3 days)
            day_diff = (day.date - today).days
            if 0 <= day_diff <= 3 and self._weather_provider:
                # Use first activity location coords or fallback estimate
                lat, lon = None, None
                for item in day.items or []:
                    loc = getattr(item, "location", None)
                    if loc and hasattr(loc, "latitude") and loc.latitude:
                        lat, lon = loc.latitude, loc.longitude
                        break

                if lat is not None and lon is not None:
                    forecast = await self._weather_provider.get_forecast(lat, lon, day.date)
                    if forecast and forecast.is_severe_advisory:
                        for uid in recipients:
                            dedup = f"weather:alert:{trip.entity_id}:{day.date}:{uid}"
                            msg = forecast.advisory_message or f"Advisory for Day {day.day_number}: {forecast.summary}"
                            dispatched = await self._notification_service.send_categorized_notification(
                                user_id=uid,
                                category=NotificationCategory.WEATHER_ALERTS,
                                dedup_key=dedup,
                                trip_id=trip.entity_id.value if hasattr(trip.entity_id, "value") else trip.entity_id,
                                title=f"Weather Alert: Day {day.day_number}",
                                body=msg,
                                payload={"type": "weather_alert", "trip_id": str(trip.entity_id), "date": str(day.date)},
                            )
                            if dispatched:
                                wtr_sent += 1

            # Activity 2-hour reminder for today
            if day.date == today:
                for item in day.items or []:
                    if not item.start_time:
                        continue

                    act_dt = datetime.combine(today, item.start_time, tzinfo=tz)
                    time_diff = (act_dt - now_dt).total_seconds()

                    # Trigger between 90 minutes and 150 minutes (~2 hours) before activity
                    if 5400 <= time_diff <= 9000:
                        for uid in recipients:
                            dedup = f"reminder:activity:{item.entity_id}:{today}:{uid}"
                            dispatched = await self._notification_service.send_categorized_notification(
                                user_id=uid,
                                category=NotificationCategory.ITINERARY_REMINDERS,
                                dedup_key=dedup,
                                trip_id=trip.entity_id.value if hasattr(trip.entity_id, "value") else trip.entity_id,
                                title=f"Upcoming: {item.title}",
                                body=f"Starting in 2 hours ({item.start_time.strftime('%H:%M')}).",
                                payload={"type": "activity_reminder", "trip_id": str(trip.entity_id), "item_id": str(item.entity_id)},
                            )
                            if dispatched:
                                act_sent += 1

        return act_sent, wtr_sent

    async def _check_proactive_warnings(self, trip: Trip) -> int:
        """Run ProactiveIntelligenceService and alert on HIGH/CRITICAL issues."""
        if not self._proactive_intelligence:
            return 0

        raw_warnings = []
        if hasattr(self._proactive_intelligence, "evaluate_trip_warnings"):
            raw_warnings = await self._proactive_intelligence.evaluate_trip_warnings(trip.entity_id)
        elif hasattr(self._proactive_intelligence, "analyze_trip"):
            res = await self._proactive_intelligence.analyze_trip(trip.entity_id)
            raw_warnings = getattr(res, "warnings", [])

        if not raw_warnings:
            return 0

        recipients = await self._get_trip_recipients(trip)
        sent_count = 0
        today_str = date.today().isoformat()

        for warning in raw_warnings:
            # Only push notify high severity / critical warnings
            sev = getattr(warning, "severity", None)
            sev_str = sev.value if hasattr(sev, "value") else str(sev or "medium")
            if sev_str.lower() in ("high", "critical"):
                for uid in recipients:
                    w_code = getattr(warning, "code", getattr(warning, "category", "warning"))
                    w_code_str = w_code.value if hasattr(w_code, "value") else str(w_code)
                    dedup = f"warning:{trip.entity_id}:{w_code_str}:{today_str}:{uid}"
                    w_title = getattr(warning, "title", "Schedule Issue")
                    w_msg = getattr(warning, "message", getattr(warning, "description", "An itinerary conflict or travel delay risk was detected."))
                    dispatched = await self._notification_service.send_categorized_notification(
                        user_id=uid,
                        category=NotificationCategory.TRAVEL_WARNINGS,
                        dedup_key=dedup,
                        trip_id=trip.entity_id.value if hasattr(trip.entity_id, "value") else trip.entity_id,
                        title=f"Travel Warning: {w_title}",
                        body=str(w_msg),
                        payload={"type": "travel_warning", "trip_id": str(trip.entity_id), "warning_code": w_code_str},
                    )
                    if dispatched:
                        sent_count += 1

        return sent_count
