"""Deterministic mock weather provider for tests and offline simulation."""

from __future__ import annotations

from datetime import date
from app.modules.travel.weather.domain.provider import (
    IWeatherProvider,
    WeatherCondition,
    WeatherForecast,
)


class MockWeatherProvider(IWeatherProvider):
    """Predictable mock weather provider."""

    def __init__(
        self,
        default_condition: WeatherCondition = WeatherCondition.SUNNY,
        is_severe: bool = False,
        advisory_msg: str | None = None,
    ) -> None:
        self.default_condition = default_condition
        self.is_severe = is_severe
        self.advisory_msg = advisory_msg

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_date: date,
    ) -> WeatherForecast | None:
        return WeatherForecast(
            date=forecast_date,
            condition=self.default_condition,
            temp_min_celsius=18.0,
            temp_max_celsius=26.0,
            precipitation_probability=80 if self.default_condition in (WeatherCondition.RAIN, WeatherCondition.HEAVY_RAIN, WeatherCondition.THUNDERSTORM) else 10,
            wind_speed_kmh=45.0 if self.is_severe else 12.0,
            summary=f"Forecast for {forecast_date}: {self.default_condition.value.replace('_', ' ').title()}",
            is_severe_advisory=self.is_severe,
            advisory_message=self.advisory_msg,
        )
