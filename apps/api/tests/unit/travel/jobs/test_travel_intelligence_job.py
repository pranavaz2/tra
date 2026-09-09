"""Unit tests for ScheduledTravelIntelligenceJob."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.dtos.assistant_dtos import (
    TravelWarningDTO,
    TripWarningsDTO,
)
from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
)
from app.modules.travel.assistant.domain.value_objects.travel_warning import (
    TravelWarning,
)
from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.jobs.travel_intelligence_job import (
    ScheduledTravelIntelligenceJob,
)
from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.weather.domain.provider import (
    IWeatherProvider,
    WeatherCondition,
    WeatherForecast,
)


@pytest.mark.asyncio
async def test_travel_intelligence_job_departure_reminders():
    """Verify departure countdown reminder is triggered 7 days and 24 hours prior."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip_7d = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Paris Summer"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today + date.resolution * 7, today + date.resolution * 14),
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip_7d])

    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=None)

    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)

    weather_provider = MagicMock(spec=IWeatherProvider)

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    stats = await job.execute()

    assert stats["trips_evaluated"] == 1
    assert stats["trip_reminders_sent"] == 1
    assert notif_service.send_categorized_notification.call_count == 1
    call_args = notif_service.send_categorized_notification.call_args[1]
    assert call_args["category"] == NotificationCategory.TRIP_REMINDERS
    assert "1 Week Until Paris Summer" in call_args["title"]


@pytest.mark.asyncio
async def test_travel_intelligence_job_severe_weather_alert():
    """Verify severe weather forecast triggers weather alert notification."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Alps Hiking"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today, today + date.resolution * 5),
    )

    itin_id = ItineraryId(uuid.uuid4())
    day_id = ItineraryDayId(uuid.uuid4())
    item_id = ItineraryItemId(uuid.uuid4())

    day1 = ItineraryDay(
        entity_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        date=today,
        title="Summit Trek",
        items=[],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1],
        version=1,
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])

    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=itinerary)

    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)

    # Weather provider returning severe thunderstorm advisory
    weather_provider = MagicMock(spec=IWeatherProvider)
    weather_provider.get_forecast = AsyncMock(
        return_value=WeatherForecast(
            date=today,
            condition=WeatherCondition.THUNDERSTORM,
            temp_min_celsius=10.0,
            temp_max_celsius=18.0,
            precipitation_probability=95,
            wind_speed_kmh=65.0,
            summary="Severe thunderstorm warning",
            is_severe_advisory=True,
            advisory_message="Heavy rain and lightning hazard.",
        )
    )

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    # Mock location lookup for day1
    loc_mock = MagicMock()
    loc_mock.latitude = 45.8326
    loc_mock.longitude = 6.8652
    day1.items = [
        ItineraryItem(
            entity_id=item_id,
            day_id=day_id,
            title=ItemTitle("Trail Start"),
            item_type=ItineraryItemType.ACTIVITY,
            location_id=None,
        )
    ]
    day1.items[0].location = loc_mock

    stats = await job.execute()

    assert stats["weather_alerts_sent"] == 1
    call_args = notif_service.send_categorized_notification.call_args[1]
    assert call_args["category"] == NotificationCategory.WEATHER_ALERTS
    assert "Weather Alert" in call_args["title"]
    assert "Heavy rain" in call_args["body"]


@pytest.mark.asyncio
async def test_travel_intelligence_job_24h_departure_reminder():
    """Verify 24-hour departure countdown reminder is triggered."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip_24h = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Goa Beach Escape"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today + date.resolution * 1, today + date.resolution * 4),
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip_24h])

    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=None)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)
    weather_provider = MagicMock(spec=IWeatherProvider)

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    stats = await job.execute()

    assert stats["trips_evaluated"] == 1
    assert stats["trip_reminders_sent"] == 1
    call_args = notif_service.send_categorized_notification.call_args[1]
    assert call_args["category"] == NotificationCategory.TRIP_REMINDERS
    assert "Tomorrow" in call_args["title"]
    assert "Goa Beach Escape" in call_args["title"]


@pytest.mark.asyncio
async def test_travel_intelligence_job_activity_reminder_2h():
    """Verify ~2-hour upcoming activity reminder is dispatched."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()
    from datetime import datetime as dt_cls
    from datetime import timedelta as td_cls
    from zoneinfo import ZoneInfo

    # Activity starting ~2 hours from now
    now_local = dt_cls.now(ZoneInfo("UTC"))
    target_start = (now_local + td_cls(hours=2)).time()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Rome Exploration"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today, today + date.resolution * 3),
    )

    itin_id = ItineraryId(uuid.uuid4())
    day_id = ItineraryDayId(uuid.uuid4())
    item_id = ItineraryItemId(uuid.uuid4())

    item = ItineraryItem(
        entity_id=item_id,
        day_id=day_id,
        title=ItemTitle("Colosseum Guided Tour"),
        item_type=ItineraryItemType.ACTIVITY,
        location_id=None,
        start_time=target_start,
        end_time=(now_local + td_cls(hours=4)).time(),
    )

    day1 = ItineraryDay(
        entity_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        date=today,
        title="Ancient Rome",
        items=[item],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1],
        version=1,
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])
    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=itinerary)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)
    weather_provider = MagicMock(spec=IWeatherProvider)
    weather_provider.get_forecast = AsyncMock(return_value=None)

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    stats = await job.execute()

    assert stats["activity_reminders_sent"] == 1
    call_args = notif_service.send_categorized_notification.call_args[1]
    assert call_args["category"] == NotificationCategory.ITINERARY_REMINDERS
    assert "Colosseum Guided Tour" in call_args["title"]
    assert "2 hours" in call_args["body"]


@pytest.mark.asyncio
async def test_travel_intelligence_job_normal_weather_no_false_alerts():
    """Verify normal sunny/cloudy weather does not generate false alerts."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Sunny Beach"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today, today + date.resolution * 3),
    )

    itin_id = ItineraryId(uuid.uuid4())
    day_id = ItineraryDayId(uuid.uuid4())
    item_id = ItineraryItemId(uuid.uuid4())

    loc_mock = MagicMock()
    loc_mock.latitude = 15.2993
    loc_mock.longitude = 74.1240

    item = ItineraryItem(
        entity_id=item_id,
        day_id=day_id,
        title=ItemTitle("Beach Relaxation"),
        item_type=ItineraryItemType.ACTIVITY,
        location_id=None,
    )
    item.location = loc_mock

    day1 = ItineraryDay(
        entity_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        date=today,
        title="Day 1",
        items=[item],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1],
        version=1,
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])
    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=itinerary)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)

    # Weather provider returning normal pleasant forecast
    weather_provider = MagicMock(spec=IWeatherProvider)
    weather_provider.get_forecast = AsyncMock(
        return_value=WeatherForecast(
            date=today,
            condition=WeatherCondition.SUNNY,
            temp_min_celsius=24.0,
            temp_max_celsius=31.0,
            precipitation_probability=10,
            wind_speed_kmh=12.0,
            summary="Sunny and warm",
            is_severe_advisory=False,
            advisory_message=None,
        )
    )

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    stats = await job.execute()

    # Zero weather alerts should be dispatched
    assert stats["weather_alerts_sent"] == 0


@pytest.mark.asyncio
async def test_travel_intelligence_job_weather_failure_graceful_fallback():
    """Verify external weather provider exception or timeout does not crash the job."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Mountain Trek"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today, today + date.resolution * 3),
    )

    itin_id = ItineraryId(uuid.uuid4())
    day_id = ItineraryDayId(uuid.uuid4())
    item_id = ItineraryItemId(uuid.uuid4())

    loc_mock = MagicMock()
    loc_mock.latitude = 32.2396
    loc_mock.longitude = 77.1887

    item = ItineraryItem(
        entity_id=item_id,
        day_id=day_id,
        title=ItemTitle("Basecamp Trek"),
        item_type=ItineraryItemType.ACTIVITY,
        location_id=None,
    )
    item.location = loc_mock

    day1 = ItineraryDay(
        entity_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        date=today,
        title="Day 1",
        items=[item],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1],
        version=1,
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])
    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=itinerary)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)

    # Weather provider raises network timeout
    weather_provider = MagicMock(spec=IWeatherProvider)
    weather_provider.get_forecast = AsyncMock(side_effect=TimeoutError("Weather API timeout"))

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    # Execution should succeed without throwing
    stats = await job.execute()
    assert stats["trips_evaluated"] == 1
    assert stats["weather_alerts_sent"] == 0


@pytest.mark.asyncio
async def test_travel_intelligence_job_proactive_conflict_warning():
    """Verify critical itinerary conflict triggers proactive warning notification."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Kyoto Highlights"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today, today + date.resolution * 3),
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])
    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=None)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)

    # Proactive intelligence returns critical conflict
    warning_mock = MagicMock()
    warning_mock.severity = "critical"
    warning_mock.code = "SCHEDULE_OVERLAP"
    warning_mock.title = "Overlapping Activities"
    warning_mock.message = "Fushimi Inari and Kinkaku-ji are scheduled at the same time."

    proactive_mock = MagicMock(spec=ProactiveIntelligenceService)
    proactive_mock.evaluate_trip_warnings = AsyncMock(return_value=[warning_mock])

    weather_provider = MagicMock(spec=IWeatherProvider)

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=proactive_mock,
    )

    stats = await job.execute()

    assert stats["travel_warnings_sent"] == 1
    call_args = notif_service.send_categorized_notification.call_args[1]
    assert call_args["category"] == NotificationCategory.TRAVEL_WARNINGS
    assert "Overlapping Activities" in call_args["title"]


@pytest.mark.asyncio
async def test_travel_intelligence_job_strict_non_mutation():
    """Verify scheduled job strictly never mutates trip, itinerary, or budget states."""
    owner_id = UserId(uuid.uuid4())
    trip_id = TripId(uuid.uuid4())
    today = date.today()

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Read-Only Guarantee"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(today + date.resolution * 7, today + date.resolution * 10),
    )
    original_title = trip.title
    original_version = trip.version

    itin_id = ItineraryId(uuid.uuid4())
    day_id = ItineraryDayId(uuid.uuid4())

    day1 = ItineraryDay(
        entity_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        date=today + date.resolution * 7,
        title="Day 1",
        items=[],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1],
        version=4,
    )

    trip_repo = MagicMock()
    trip_repo.list_active_upcoming = AsyncMock(return_value=[trip])
    itin_repo = MagicMock()
    itin_repo.find_by_trip_id = AsyncMock(return_value=itinerary)
    budget_repo = MagicMock()
    sharing_repo = MagicMock()
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    notif_service = MagicMock(spec=NotificationService)
    notif_service.send_categorized_notification = AsyncMock(return_value=True)
    weather_provider = MagicMock(spec=IWeatherProvider)

    job = ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itin_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notif_service,
        weather_provider=weather_provider,
        proactive_intelligence=None,
    )

    await job.execute()

    # Assert entities remain 100% identical and unmutated
    assert trip.title == original_title
    assert trip.version == original_version
    assert itinerary.version == 4
    assert len(itinerary.days) == 1

