"""Unit tests for weather providers."""

from __future__ import annotations

from datetime import date
import pytest

from app.modules.travel.weather.domain.provider import (
    WeatherCondition,
    WeatherForecast,
)
from app.modules.travel.weather.infrastructure.providers.mock_weather_provider import (
    MockWeatherProvider,
)
from app.modules.travel.weather.infrastructure.providers.open_meteo_provider import (
    OpenMeteoWeatherProvider,
)


@pytest.mark.asyncio
async def test_mock_weather_provider():
    """Verify MockWeatherProvider returns structured forecast and advisory."""
    provider = MockWeatherProvider(
        default_condition=WeatherCondition.HEAVY_RAIN,
        is_severe=True,
        advisory_msg="Flash flood advisory.",
    )
    today = date(2026, 10, 20)

    forecast = await provider.get_forecast(35.6762, 139.6503, today)

    assert forecast is not None
    assert forecast.date == today
    assert forecast.condition == WeatherCondition.HEAVY_RAIN
    assert forecast.is_severe_advisory is True
    assert forecast.advisory_message == "Flash flood advisory."
    assert forecast.precipitation_probability == 80


def test_open_meteo_wmo_code_mapping():
    """Verify WMO weather codes are mapped accurately."""
    provider = OpenMeteoWeatherProvider()

    assert provider._map_wmo_code(0) == WeatherCondition.SUNNY
    assert provider._map_wmo_code(2) == WeatherCondition.PARTLY_CLOUDY
    assert provider._map_wmo_code(3) == WeatherCondition.CLOUDY
    assert provider._map_wmo_code(61) == WeatherCondition.RAIN
    assert provider._map_wmo_code(65) == WeatherCondition.HEAVY_RAIN
    assert provider._map_wmo_code(95) == WeatherCondition.THUNDERSTORM
    assert provider._map_wmo_code(71) == WeatherCondition.SNOW
    assert provider._map_wmo_code(999) == WeatherCondition.UNKNOWN
