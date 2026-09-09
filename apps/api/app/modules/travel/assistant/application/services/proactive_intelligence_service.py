"""ProactiveIntelligenceService — Detects itinerary conflicts, travel feasibility issues, and budget risks."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import logging
import math
from typing import Any
from uuid import UUID

from app.modules.locations.repository import LocationRepository
from app.modules.travel.assistant.application.dtos.assistant_dtos import (
    TravelWarningDTO,
    TripWarningsDTO,
)
from app.modules.travel.assistant.domain.enums import (
    WarningCategory,
    WarningSeverity,
)
from app.modules.travel.assistant.domain.value_objects.travel_warning import (
    TravelWarning,
)
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.services.maps.base import PlacesProvider
from app.services.maps.route import RouteDetails, RoutingProvider, TravelMode

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two geographic coordinates in kilometers."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_km * c


class ProactiveIntelligenceService:
    """Evaluates trip state to discover proactive itinerary conflicts, distance feasibility, and budget risks."""

    def __init__(
        self,
        itinerary_repository: IItineraryRepository,
        budget_repository: ITripBudgetRepository,
        location_repository: LocationRepository | None = None,
        places_provider: PlacesProvider | None = None,
        routing_provider: RoutingProvider | None = None,
    ) -> None:
        self._itinerary_repo = itinerary_repository
        self._budget_repo = budget_repository
        self._location_repo = location_repository
        self._places_provider = places_provider
        self._routing_provider = routing_provider


    async def evaluate_trip_warnings(self, trip_id: TripId) -> list[TravelWarning]:
        """Evaluate itinerary, travel feasibility, and budget for any proactive warnings."""
        warnings: list[TravelWarning] = []
        seen_keys: set[str] = set()

        def add_warning(w: TravelWarning) -> None:
            dedup_key = f"{w.category.value}:{w.title}:{w.message}:{w.day_number}"
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                warnings.append(w)

        # 1. Evaluate Itinerary Conflicts & Feasibility
        itinerary = await self._itinerary_repo.find_by_trip_id(trip_id)
        if itinerary and not itinerary.is_deleted:
            itin_warnings = await self._evaluate_itinerary(itinerary)
            for w in itin_warnings:
                add_warning(w)

        # 2. Evaluate Budget Risks
        budget = await self._budget_repo.find_by_trip_id(trip_id)
        if budget and not budget.is_deleted:
            budget_warnings = self._evaluate_budget(budget)
            for w in budget_warnings:
                add_warning(w)

        return warnings

    async def get_trip_warnings_dto(self, trip_id: TripId) -> TripWarningsDTO:
        """Return structured DTO summarizing proactive warnings for the given trip."""
        domain_warnings = await self.evaluate_trip_warnings(trip_id)

        dtos = [
            TravelWarningDTO(
                warning_id=w.warning_id,
                category=w.category.value,
                severity=w.severity.value,
                title=w.title,
                message=w.message,
                day_number=w.day_number,
                item_ids=w.item_ids,
                metadata=dict(w.metadata),
            )
            for w in domain_warnings
        ]

        has_crit = any(w.severity == WarningSeverity.CRITICAL for w in domain_warnings)
        itinerary_count = sum(
            1 for w in domain_warnings
            if w.category in (WarningCategory.TIMING, WarningCategory.DISTANCE, WarningCategory.FEASIBILITY)
        )
        budget_count = sum(
            1 for w in domain_warnings if w.category == WarningCategory.BUDGET
        )

        return TripWarningsDTO(
            trip_id=trip_id.value,
            warnings=tuple(dtos),
            total_warnings=len(dtos),
            has_critical=has_crit,
            itinerary_conflicts_count=itinerary_count,
            budget_risks_count=budget_count,
        )

    async def _evaluate_itinerary(self, itinerary: Itinerary) -> list[TravelWarning]:
        """Check for time contradictions, overlapping activities, tight intervals, and distant locations."""
        warnings: list[TravelWarning] = []

        for day in itinerary.days:
            # Step A: Validate individual item times
            for item in day.items:
                if item.start_time and item.end_time:
                    if item.end_time <= item.start_time:
                        warnings.append(
                            TravelWarning(
                                warning_id=f"invalid_time_{item.entity_id.value}",
                                category=WarningCategory.TIMING,
                                severity=WarningSeverity.CRITICAL,
                                title="Invalid Activity Schedule",
                                message=(
                                    f"Activity '{item.title.value}' on Day {day.day_number} has an end time "
                                    f"({item.end_time.strftime('%H:%M')}) that is earlier than or equal to its start time "
                                    f"({item.start_time.strftime('%H:%M')})."
                                ),
                                day_number=day.day_number,
                                item_ids=(str(item.entity_id.value),),
                                metadata={
                                    "start_time": item.start_time.strftime("%H:%M"),
                                    "end_time": item.end_time.strftime("%H:%M"),
                                },
                            )
                        )

            # Step B: Check consecutive and overlapping items on this day
            timed_items = [
                item for item in day.items
                if item.start_time is not None
            ]
            timed_items.sort(key=lambda x: x.start_time)  # type: ignore[arg-type]

            for i in range(len(timed_items) - 1):
                item_a = timed_items[i]
                item_b = timed_items[i + 1]

                # Case 1: Overlapping activities
                if item_a.end_time and item_b.start_time < item_a.end_time:
                    warnings.append(
                        TravelWarning(
                            warning_id=f"overlap_{item_a.entity_id.value}_{item_b.entity_id.value}",
                            category=WarningCategory.TIMING,
                            severity=WarningSeverity.WARNING,
                            title="Schedule Overlap",
                            message=(
                                f"Activities '{item_a.title.value}' ({item_a.start_time.strftime('%H:%M')}-{item_a.end_time.strftime('%H:%M')}) "
                                f"and '{item_b.title.value}' ({item_b.start_time.strftime('%H:%M')}"
                                + (f"-{item_b.end_time.strftime('%H:%M')}" if item_b.end_time else "")
                                + f") overlap on Day {day.day_number}."
                            ),
                            day_number=day.day_number,
                            item_ids=(str(item_a.entity_id.value), str(item_b.entity_id.value)),
                            metadata={
                                "item_a_time": f"{item_a.start_time.strftime('%H:%M')}-{item_a.end_time.strftime('%H:%M')}",
                                "item_b_time": f"{item_b.start_time.strftime('%H:%M')}" + (f"-{item_b.end_time.strftime('%H:%M')}" if item_b.end_time else ""),
                            },
                        )
                    )
                    continue

                # Case 2: Feasibility & transit interval between consecutive items
                if item_a.end_time and item_b.start_time >= item_a.end_time:
                    gap_seconds = (
                        datetime.combine(date.min, item_b.start_time)
                        - datetime.combine(date.min, item_a.end_time)
                    ).total_seconds()
                    gap_minutes = int(gap_seconds // 60)

                    coords_a = await self._resolve_coordinates(item_a)
                    coords_b = await self._resolve_coordinates(item_b)

                    if coords_a and coords_b:
                        lat_a, lon_a = coords_a
                        lat_b, lon_b = coords_b
                        route: RouteDetails | None = None

                        if self._routing_provider:
                            try:
                                route = await self._routing_provider.get_route(
                                    (lat_a, lon_a), (lat_b, lon_b), travel_mode=TravelMode.DRIVE.value
                                )
                            except Exception as exc:
                                logger.debug("Routing lookup failed between %s and %s: %s", item_a.entity_id, item_b.entity_id, exc)

                        if route:
                            drive_minutes = route.duration_minutes
                            route_km = route.distance_km

                            if gap_minutes < drive_minutes:
                                severity = (
                                    WarningSeverity.CRITICAL
                                    if gap_minutes <= max(5, drive_minutes // 2)
                                    else WarningSeverity.WARNING
                                )
                                if route.is_fallback:
                                    msg = (
                                        f"Only {gap_minutes} minutes between these activities, but the "
                                        f"estimated travel distance is approximately {route_km:.1f} km (est. {drive_minutes} mins)."
                                    )
                                else:
                                    msg = (
                                        f"Only {gap_minutes} minutes between these activities, but the "
                                        f"estimated drive time is {drive_minutes} minutes ({route_km:.1f} km)."
                                    )

                                warnings.append(
                                    TravelWarning(
                                        warning_id=f"insufficient_travel_time_{item_a.entity_id.value}_{item_b.entity_id.value}",
                                        category=WarningCategory.DISTANCE,
                                        severity=severity,
                                        title="Insufficient Travel Time",
                                        message=msg,
                                        day_number=day.day_number,
                                        item_ids=(str(item_a.entity_id.value), str(item_b.entity_id.value)),
                                        metadata={
                                            "estimated_duration_minutes": drive_minutes,
                                            "route_distance_km": route_km,
                                            "travel_mode": route.travel_mode,
                                            "gap_minutes": gap_minutes,
                                            "is_fallback": route.is_fallback,
                                            "is_verified_coordinates": True,
                                        },
                                    )
                                )
                                continue
                            elif gap_minutes < drive_minutes + 10 and drive_minutes >= 30:
                                warnings.append(
                                    TravelWarning(
                                        warning_id=f"tight_route_buffer_{item_a.entity_id.value}_{item_b.entity_id.value}",
                                        category=WarningCategory.DISTANCE,
                                        severity=WarningSeverity.INFO,
                                        title="Tight Travel Buffer",
                                        message=(
                                            f"Estimated drive time is {drive_minutes} minutes ({route_km:.1f} km) "
                                            f"with a {gap_minutes}-minute scheduled interval."
                                        ),
                                        day_number=day.day_number,
                                        item_ids=(str(item_a.entity_id.value), str(item_b.entity_id.value)),
                                        metadata={
                                            "estimated_duration_minutes": drive_minutes,
                                            "route_distance_km": route_km,
                                            "travel_mode": route.travel_mode,
                                            "gap_minutes": gap_minutes,
                                            "is_fallback": route.is_fallback,
                                            "is_verified_coordinates": True,
                                        },
                                    )
                                )
                                continue
                        else:
                            # Fallback to straight-line Haversine heuristic if routing is unavailable
                            dist_km = haversine_distance_km(lat_a, lon_a, lat_b, lon_b)
                            is_unrealistic = False
                            if dist_km >= 5.0 and gap_minutes <= 10:
                                is_unrealistic = True
                            elif dist_km >= 10.0 and gap_minutes <= 20:
                                is_unrealistic = True
                            elif gap_minutes > 0 and (dist_km / (gap_minutes / 60.0)) > 45.0:
                                is_unrealistic = True

                            if is_unrealistic:
                                warnings.append(
                                    TravelWarning(
                                        warning_id=f"distance_feasibility_{item_a.entity_id.value}_{item_b.entity_id.value}",
                                        category=WarningCategory.DISTANCE,
                                        severity=WarningSeverity.WARNING,
                                        title="Tight Travel Feasibility",
                                        message=(
                                            f"Only {gap_minutes} minutes between these activities, but they are "
                                            f"approximately {dist_km:.1f} km apart."
                                        ),
                                        day_number=day.day_number,
                                        item_ids=(str(item_a.entity_id.value), str(item_b.entity_id.value)),
                                        metadata={
                                            "estimated_distance_km": round(dist_km, 1),
                                            "gap_minutes": gap_minutes,
                                            "is_verified_coordinates": True,
                                            "is_fallback": True,
                                        },
                                    )
                                )
                                continue

                    # Case 3: Tight schedule buffer without coordinates or within same venue
                    if gap_minutes < 10:
                        severity = WarningSeverity.WARNING if gap_minutes == 0 else WarningSeverity.INFO
                        warnings.append(
                            TravelWarning(
                                warning_id=f"insufficient_gap_{item_a.entity_id.value}_{item_b.entity_id.value}",
                                category=WarningCategory.TIMING,
                                severity=severity,
                                title="Tight Schedule Buffer",
                                message=(
                                    f"Only {gap_minutes} minutes between consecutive activities "
                                    f"'{item_a.title.value}' and '{item_b.title.value}' on Day {day.day_number}. "
                                    "Consider adding a buffer for transit."
                                ),
                                day_number=day.day_number,
                                item_ids=(str(item_a.entity_id.value), str(item_b.entity_id.value)),
                                metadata={"gap_minutes": gap_minutes},
                            )
                        )


        return warnings

    def _evaluate_budget(self, budget: TripBudget) -> list[TravelWarning]:
        """Check for budget limit overages, high spending utilization, and category overages."""
        warnings: list[TravelWarning] = []

        # 1. Total budget limit check
        if budget.limit and budget.limit.amount > Decimal("0.00"):
            limit_amt = float(budget.limit.amount)
            spent_amt = float(budget.total_spent.amount) if budget.total_spent else 0.0
            currency = budget.limit.currency

            if spent_amt > limit_amt:
                warnings.append(
                    TravelWarning(
                        warning_id=f"budget_overage_{budget.entity_id.value}",
                        category=WarningCategory.BUDGET,
                        severity=WarningSeverity.CRITICAL,
                        title="Budget Exceeded",
                        message=(
                            f"Trip budget exceeded: total expenses ({spent_amt:.2f} {currency}) "
                            f"exceed your budget limit of {limit_amt:.2f} {currency}."
                        ),
                        metadata={
                            "total_spent": spent_amt,
                            "limit": limit_amt,
                            "currency": currency,
                        },
                    )
                )
            elif budget.spent_percentage >= 90.0:
                remaining_amt = float(budget.remaining_budget.amount) if budget.remaining_budget else 0.0
                warnings.append(
                    TravelWarning(
                        warning_id=f"budget_utilization_{budget.entity_id.value}",
                        category=WarningCategory.BUDGET,
                        severity=WarningSeverity.WARNING,
                        title="High Budget Utilization",
                        message=(
                            f"Budget warning: You have spent {budget.spent_percentage:.0f}% of your "
                            f"{limit_amt:.2f} {currency} budget with {remaining_amt:.2f} {currency} remaining."
                        ),
                        metadata={
                            "spent_percentage": budget.spent_percentage,
                            "remaining": remaining_amt,
                            "limit": limit_amt,
                            "currency": currency,
                        },
                    )
                )

        # 2. Category allocation checks
        cat_spending: dict[Any, Decimal] = {}
        for exp in budget.expenses:
            cat_spending[exp.category_id] = cat_spending.get(exp.category_id, Decimal("0.00")) + exp.amount.amount

        for category in budget.categories:
            allocated = getattr(category, "allocated_amount", None)
            if allocated and getattr(allocated, "amount", None) is not None:
                cat_allocated = float(allocated.amount)
                cat_spent = float(cat_spending.get(category.entity_id, Decimal("0.00")))
                currency = getattr(allocated, "currency", getattr(budget.limit, "currency", "USD"))

                if cat_allocated > 0 and cat_spent > cat_allocated:
                    warnings.append(
                        TravelWarning(
                            warning_id=f"category_overage_{category.entity_id.value}",
                            category=WarningCategory.BUDGET,
                            severity=WarningSeverity.WARNING,
                            title="Category Budget Exceeded",
                            message=(
                                f"Category '{category.name}' has exceeded its allocation: spent "
                                f"{cat_spent:.2f} {currency} of {cat_allocated:.2f} {currency}."
                            ),
                            metadata={
                                "category_id": str(category.entity_id.value),
                                "category_name": category.name,
                                "allocated": cat_allocated,
                                "spent": cat_spent,
                                "currency": currency,
                            },
                        )
                    )

        return warnings

    async def _resolve_coordinates(self, item: ItineraryItem) -> tuple[float, float] | None:
        """Resolve latitude and longitude for an itinerary item safely without raising exceptions."""
        try:
            if item.location_id and self._location_repo:
                loc = await self._location_repo.get_by_id(item.location_id)
                if loc and loc.latitude is not None and loc.longitude is not None:
                    return (float(loc.latitude), float(loc.longitude))
        except Exception as exc:
            logger.debug("Failed to resolve location coordinates for item %s: %s", item.entity_id, exc)

        return None
