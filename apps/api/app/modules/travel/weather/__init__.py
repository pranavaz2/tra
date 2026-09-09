"""Weather module exports."""

from app.modules.travel.weather.domain.provider import (
    IWeatherProvider,
    WeatherCondition,
    WeatherForecast,
)
from app.modules.travel.weather.infrastructure.providers.mock_weather_provider import (
    MockWeatherProvider,
)
from app.modules.travel.weather.infrastructure.providers.open_meteo_provider import (
    OpenMeteoWeatherProvider,
)

__all__ = [
    "IWeatherProvider",
    "WeatherCondition",
    "WeatherForecast",
    "MockWeatherProvider",
    "OpenMeteoWeatherProvider",
]
