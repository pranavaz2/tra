"""Weather provider domain interface and value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import enum
from typing import Protocol, runtime_checkable


class WeatherCondition(str, enum.Enum):
    """Normalized weather condition categories."""

    SUNNY = "sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    WINDY = "windy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WeatherForecast:
    """Daily or point-in-time weather forecast."""

    date: date
    condition: WeatherCondition
    temp_min_celsius: float
    temp_max_celsius: float
    precipitation_probability: int  # 0 - 100
    wind_speed_kmh: float
    summary: str
    is_severe_advisory: bool = False
    advisory_message: str | None = None


@runtime_checkable
class IWeatherProvider(Protocol):
    """Abstract port for querying weather forecasts."""

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_date: date,
    ) -> WeatherForecast | None:
        """Fetch forecasted weather for given coordinates and date."""
        ...
