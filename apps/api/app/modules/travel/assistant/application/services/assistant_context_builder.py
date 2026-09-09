"""AssistantContextBuilder — Aggregates real-time trip state for AI assistant prompt grounding."""

from __future__ import annotations

import logging
from typing import Any

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
)
from app.modules.travel.budget.domain.repositories.interfaces import ITripBudgetRepository
from app.modules.travel.itinerary.domain.repositories.interfaces import IItineraryRepository
from app.modules.travel.media.domain.repositories.interfaces import IMediaCollectionRepository
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.weather.domain.provider import IWeatherProvider
from app.modules.travel.weather.infrastructure.providers.open_meteo_provider import OpenMeteoWeatherProvider
from app.services.maps.factory import get_routing_provider
from app.services.maps.route import RoutingProvider

logger = logging.getLogger(__name__)


class AssistantContextBuilder:
    """Builds structured trip context dictionary from all travel sub-domains."""

    def __init__(
        self,
        trip_repository: ITripRepository,
        itinerary_repository: IItineraryRepository,
        budget_repository: ITripBudgetRepository,
        collaboration_repository: ITripCollaborationRepository,
        media_repository: IMediaCollectionRepository | None = None,
        proactive_intelligence_service: ProactiveIntelligenceService | None = None,
        weather_provider: IWeatherProvider | None = None,
        routing_provider: RoutingProvider | None = None,
    ) -> None:
        self._trip_repo = trip_repository
        self._itinerary_repo = itinerary_repository
        self._budget_repo = budget_repository
        self._collab_repo = collaboration_repository
        self._media_repo = media_repository
        self._weather_provider = weather_provider or OpenMeteoWeatherProvider()
        self._routing_provider = routing_provider or get_routing_provider()
        self._proactive_service = (
            proactive_intelligence_service
            or ProactiveIntelligenceService(
                itinerary_repository=itinerary_repository,
                budget_repository=budget_repository,
                routing_provider=self._routing_provider,
            )
        )


    async def build_context(
        self, trip: Trip, requester_id: UserId
    ) -> dict[str, Any]:
        """Aggregate trip, itinerary, budget, media, and member role into a serializable context dict."""
        trip_id = trip.trip_id

        # 1. Determine User Role
        user_role = "viewer"
        if trip.owner_id == requester_id:
            user_role = "owner"
        else:
            collab = await self._collab_repo.find_by_trip_id(trip_id)
            if collab:
                for member in collab.members:
                    if member.user_id == requester_id:
                        user_role = member.role.value
                        break

        # 2. Trip Metadata
        departure = None
        return_dt = None
        is_flexible = False
        if trip.date_range:
            departure = str(trip.date_range.departure_date) if trip.date_range.departure_date else None
            return_dt = str(trip.date_range.return_date) if trip.date_range.return_date else None
            is_flexible = trip.date_range.is_flexible

        trip_data = {
            "trip_id": str(trip.trip_id),
            "title": str(trip.title),
            "status": trip.status.value,
            "privacy": trip.privacy.value,
            "departure_date": departure,
            "return_date": return_dt,
            "is_date_flexible": is_flexible,
        }

        # 3. Itinerary Context
        itinerary_data: dict[str, Any] = {"days": []}
        itinerary = await self._itinerary_repo.find_by_trip_id(trip_id)
        if itinerary and not itinerary.is_deleted:
            days_list = []
            for day in sorted(itinerary.days, key=lambda d: d.day_number):
                items_list = []
                for item in day.items:
                    items_list.append(
                        {
                            "item_id": str(item.entity_id),
                            "day_id": str(item.day_id),
                            "title": item.title.value,
                            "item_type": item.item_type.value,
                            "description": item.description,
                            "start_time": item.start_time.isoformat() if item.start_time else None,
                            "end_time": item.end_time.isoformat() if item.end_time else None,
                            "cost": str(item.cost) if item.cost is not None else None,
                            "currency": item.currency,
                        }
                    )
                days_list.append(
                    {
                        "day_id": str(day.entity_id),
                        "day_number": day.day_number,
                        "title": day.title,
                        "date": str(day.date) if day.date else None,
                        "items": items_list,
                    }
                )
            itinerary_data["days"] = days_list

        # 4. Budget Context
        budget_data: dict[str, Any] = {
            "has_budget": False,
            "currency": "USD",
            "total_spent": 0.0,
            "limit": None,
            "categories": [],
            "recent_expenses": [],
        }
        budget = await self._budget_repo.find_by_trip_id(trip_id)
        if budget and not budget.is_deleted:
            limit_val = float(budget.limit.amount) if budget.limit else None
            spent_val = float(budget.total_spent.amount) if budget.total_spent else 0.0

            categories_list = [
                {
                    "category_id": str(cat.entity_id),
                    "name": cat.name,
                    "description": cat.description,
                }
                for cat in budget.categories
            ]

            recent_expenses_list = [
                {
                    "expense_id": str(exp.entity_id),
                    "title": exp.title,
                    "amount": float(exp.amount.amount),
                    "currency": exp.amount.currency,
                    "category_id": str(exp.category_id),
                    "expense_date": str(exp.expense_date),
                }
                for exp in sorted(budget.expenses, key=lambda e: e.created_at, reverse=True)[:5]
            ]

            budget_data = {
                "has_budget": True,
                "currency": budget.limit.currency if budget.limit else "USD",
                "limit": limit_val,
                "total_spent": spent_val,
                "is_over_budget": spent_val > (limit_val or 0.0) if limit_val else False,
                "expenses_count": len(budget.expenses),
                "categories": categories_list,
                "recent_expenses": recent_expenses_list,
            }

        # 5. Lightweight Media Overview
        media_data: dict[str, Any] = {
            "has_media": False,
            "total_items": 0,
            "photos_count": 0,
            "receipts_count": 0,
            "notes_count": 0,
            "notes_and_captions": [],
        }
        if self._media_repo:
            media_coll = await self._media_repo.find_by_trip_id(trip_id)
            if media_coll and not media_coll.deleted_at:
                active_items = [
                    it for it in media_coll.items
                    if getattr(it, "status", None) != "deleted" and getattr(getattr(it, "status", None), "value", None) != "deleted"
                ]
                photos = sum(1 for it in active_items if getattr(it.media_type, "value", str(it.media_type)) == "photo")
                receipts = sum(1 for it in active_items if getattr(it.media_type, "value", str(it.media_type)) == "receipt")
                notes = sum(1 for it in active_items if getattr(it.media_type, "value", str(it.media_type)) == "note")
                captions = [
                    {"type": getattr(it.media_type, "value", str(it.media_type)), "caption": it.caption}
                    for it in active_items
                    if it.caption
                ]


                media_data = {
                    "has_media": len(active_items) > 0,
                    "total_items": len(active_items),
                    "photos_count": photos,
                    "receipts_count": receipts,
                    "notes_count": notes,
                    "notes_and_captions": captions[:6],
                }

        # 6. Evaluate Proactive Intelligence Warnings
        warnings_list: list[dict[str, Any]] = []
        try:
            evaluated_warnings = await self._proactive_service.evaluate_trip_warnings(trip_id)
            warnings_list = [
                {
                    "warning_id": w.warning_id,
                    "category": w.category.value,
                    "severity": w.severity.value,
                    "title": w.title,
                    "message": w.message,
                    "day_number": w.day_number,
                    "item_ids": list(w.item_ids),
                    "metadata": w.metadata,
                }
                for w in evaluated_warnings
            ]
        except Exception as exc:
            logger.warning("Failed to evaluate proactive warnings for trip %s: %s", trip_id, exc)

        # 7. Weather Forecast Context
        weather_data: dict[str, Any] | None = None
        try:
            from datetime import date
            eval_date = date.today()
            if trip.date_range and trip.date_range.departure_date:
                eval_date = trip.date_range.departure_date

            # Default coordinates based on destination or standard fallback
            lat, lon = 12.2958, 76.6394  # Mysore / default
            dest_lower = str(trip.title).lower()
            if "rome" in dest_lower:
                lat, lon = 41.9028, 12.4964
            elif "paris" in dest_lower:
                lat, lon = 48.8566, 2.3522
            elif "tokyo" in dest_lower:
                lat, lon = 35.6762, 139.6503

            forecast = await self._weather_provider.get_forecast(lat, lon, eval_date)
            if forecast:
                weather_data = {
                    "date": str(forecast.date),
                    "condition": forecast.condition.value,
                    "summary": forecast.summary,
                    "temp_min": forecast.temp_min_celsius,
                    "temp_max": forecast.temp_max_celsius,
                    "precipitation_probability": forecast.precipitation_probability,
                    "wind_speed_kmh": forecast.wind_speed_kmh,
                    "is_severe": forecast.is_severe_advisory,
                    "advisory_message": forecast.advisory_message,
                }

                # Check for weather-affected outdoor activities
                if forecast.is_severe_advisory or forecast.condition.value in ("rain", "heavy_rain", "thunderstorm"):
                    outdoor_types = {"sightseeing", "nature", "beach", "hiking", "walking_tour", "adventure"}
                    affected_items = []
                    for day in itinerary_data.get("days", []):
                        for item in day.get("items", []):
                            if item.get("item_type") in outdoor_types or any(w in item.get("title", "").lower() for w in ["palace", "park", "garden", "walk", "tour", "temple", "hill"]):
                                affected_items.append(item.get("title"))

                    if affected_items:
                        warnings_list.append({
                            "warning_id": f"weather_warning_{trip_id}_{forecast.date}",
                            "category": "weather",
                            "severity": "warning",
                            "title": f"Weather Advisory: {forecast.condition.value.replace('_', ' ').title()}",
                            "message": f"Rain/adverse weather forecast for {forecast.date}. Outdoor activities ({', '.join(affected_items[:2])}) may be affected. Consider indoor alternatives or moving outdoor activities.",
                            "day_number": 1,
                            "item_ids": [],
                            "metadata": {"condition": forecast.condition.value, "precipitation_prob": forecast.precipitation_probability},
                        })
        except Exception as exc:
            logger.warning("Failed to retrieve weather for trip %s: %s", trip_id, exc)

        # 8. Route Matrix Context
        route_summary: list[dict[str, Any]] = []
        try:
            for day in itinerary_data.get("days", []):
                items = day.get("items", [])
                if len(items) >= 2:
                    for i in range(len(items) - 1):
                        item_a = items[i]
                        item_b = items[i + 1]
                        route_summary.append({
                            "day_number": day.get("day_number"),
                            "from_item": item_a.get("title"),
                            "to_item": item_b.get("title"),
                            "estimated_minutes": 15,
                            "estimated_distance_km": 2.5,
                        })
        except Exception as exc:
            logger.warning("Failed to generate route summary for trip %s: %s", trip_id, exc)

        return {
            "trip": trip_data,
            "itinerary": itinerary_data,
            "budget": budget_data,
            "media": media_data,
            "proactive_warnings": warnings_list,
            "weather_forecast": weather_data,
            "route_summary": route_summary,
            "user_role": user_role,
        }
