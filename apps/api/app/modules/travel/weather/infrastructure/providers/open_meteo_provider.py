"""Open-Meteo free API weather provider implementation."""

from __future__ import annotations

from datetime import date
import logging
import httpx

from app.modules.travel.weather.domain.provider import (
    IWeatherProvider,
    WeatherCondition,
    WeatherForecast,
)

logger = logging.getLogger(__name__)


class OpenMeteoWeatherProvider(IWeatherProvider):
    """Fetches daily forecast from Open-Meteo open weather API without API key requirement."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout = timeout_seconds

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_date: date,
    ) -> WeatherForecast | None:
        url = "https://api.open-meteo.com/v1/forecast"
        date_str = forecast_date.isoformat()
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ["weathercode", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max", "windspeed_10m_max"],
            "start_date": date_str,
            "end_date": date_str,
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("Open-Meteo API returned status %s for date %s", resp.status_code, date_str)
                    return None

                data = resp.json()
                daily = data.get("daily", {})
                wcodes = daily.get("weathercode", [])
                if not wcodes:
                    return None

                wcode = wcodes[0]
                t_max = float(daily.get("temperature_2m_max", [20.0])[0])
                t_min = float(daily.get("temperature_2m_min", [12.0])[0])
                precip_prob = int(daily.get("precipitation_probability_max", [0])[0] or 0)
                wind_speed = float(daily.get("windspeed_10m_max", [10.0])[0] or 10.0)

                condition = self._map_wmo_code(wcode)
                is_severe = condition in (WeatherCondition.HEAVY_RAIN, WeatherCondition.THUNDERSTORM) or wind_speed > 60.0
                advisory = f"Severe weather advisory: {condition.value.replace('_', ' ').title()} expected with strong winds." if is_severe else None

                return WeatherForecast(
                    date=forecast_date,
                    condition=condition,
                    temp_min_celsius=t_min,
                    temp_max_celsius=t_max,
                    precipitation_probability=precip_prob,
                    wind_speed_kmh=wind_speed,
                    summary=f"Forecast: {condition.value.replace('_', ' ').title()}, {t_min:.1f}°C - {t_max:.1f}°C",
                    is_severe_advisory=is_severe,
                    advisory_message=advisory,
                )
        except Exception as exc:
            logger.warning("Weather fetch failed gracefully: %s", exc)
            return None

    def _map_wmo_code(self, code: int) -> WeatherCondition:
        if code in (0, 1):
            return WeatherCondition.SUNNY
        if code == 2:
            return WeatherCondition.PARTLY_CLOUDY
        if code == 3:
            return WeatherCondition.CLOUDY
        if code in (51, 53, 55, 61, 63, 80, 81):
            return WeatherCondition.RAIN
        if code in (65, 82):
            return WeatherCondition.HEAVY_RAIN
        if code in (95, 96, 99):
            return WeatherCondition.THUNDERSTORM
        if code in (71, 73, 75, 77, 85, 86):
            return WeatherCondition.SNOW
        return WeatherCondition.UNKNOWN
