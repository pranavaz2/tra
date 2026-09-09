"""MockAssistantEngine for deterministic local testing, places grounding, and unit tests."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.modules.travel.assistant.domain.enums import (
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.value_objects import ChatMessage
from app.modules.travel.assistant.infrastructure.engine.base import (
    AssistantEngine,
    AssistantEngineResult,
    ProposedActionData,
)
from app.services.maps.base import PlaceDetails, PlacesProvider
from app.services.maps.mock import MockPlacesProvider, MockRoutingProvider
from app.services.maps.route import RouteDetails, RoutingProvider, TravelMode

logger = logging.getLogger(__name__)


class MockAssistantEngine(AssistantEngine):
    """Deterministic Mock AI Assistant for travel planning, places grounding & trip assistance."""

    def __init__(
        self,
        places_provider: PlacesProvider | None = None,
        routing_provider: RoutingProvider | None = None,
    ) -> None:
        self._places_provider = places_provider or MockPlacesProvider()
        self._routing_provider = routing_provider or MockRoutingProvider()


    async def chat(
        self,
        *,
        context: dict[str, Any],
        user_message: str,
        history: list[ChatMessage] | None = None,
    ) -> AssistantEngineResult:
        msg_lower = user_message.lower()
        trip_title = context.get("trip", {}).get("title", "your trip")
        days = context.get("itinerary", {}).get("days", [])
        budget = context.get("budget", {})
        categories = budget.get("categories", [])
        media = context.get("media", {})

        # 1. Proactive Intelligence — Itinerary Conflicts Check
        if (
            "conflict" in msg_lower
            or "overlap" in msg_lower
            or "schedule issue" in msg_lower
            or "check_itinerary_conflicts" in msg_lower
        ):
            warnings = context.get("proactive_warnings", [])
            timing_warnings = [w for w in warnings if w.get("category") == "timing"]
            if timing_warnings:
                details = "\n".join(f"- ⚠️ {w.get('message')}" for w in timing_warnings)
                msg = f"I detected the following itinerary schedule conflicts:\n\n{details}\n\nI recommend adjusting the start or end times to prevent overlaps."
            else:
                msg = f"I inspected your schedule for '{trip_title}' and found no overlapping activities or timing conflicts. Your itinerary is well-spaced!"

            return AssistantEngineResult(
                message=msg,
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.CHECK_ITINERARY_CONFLICTS,
                ),
            )

        # 2. Proactive Intelligence — Travel Feasibility Check
        if (
            "feasibility" in msg_lower
            or "distance" in msg_lower
            or "transit" in msg_lower
            or "check_travel_feasibility" in msg_lower
        ):
            warnings = context.get("proactive_warnings", [])
            dist_warnings = [w for w in warnings if w.get("category") == "distance"]
            if dist_warnings:
                details = "\n".join(f"- ⚠️ {w.get('message')}" for w in dist_warnings)
                msg = f"I checked travel feasibility between consecutive places:\n\n{details}\n\nI recommend adding more buffer time or grouping nearby activities together."
            else:
                msg = f"Travel feasibility check passed! All consecutive activities for '{trip_title}' have sufficient transit time based on their locations."

            return AssistantEngineResult(
                message=msg,
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.CHECK_TRAVEL_FEASIBILITY,
                ),
            )

        # 2.5 Real Routing & Travel-Time Estimation
        if (
            "estimate_travel_time" in msg_lower
            or "check_route_between_activities" in msg_lower
            or "travel time" in msg_lower
            or "drive time" in msg_lower
            or "how long" in msg_lower
            or "can i reach" in msg_lower
            or "route between" in msg_lower
            or "route from" in msg_lower
        ):
            # Scan context for items
            items_found = []
            for d in days:
                for it in d.get("items", []):
                    items_found.append(it)

            if len(items_found) >= 2:
                item_a = items_found[0]
                item_b = items_found[1]
                title_a = item_a.get("title", "Activity 1")
                title_b = item_b.get("title", "Activity 2")

                # Default sample coordinates in Rome / Paris if items lack coords
                origin_coords = (41.8902, 12.4922)  # Colosseum
                dest_coords = (41.8875, 12.4772)    # Trattoria Da Enzo

                route = await self._routing_provider.get_route(origin_coords, dest_coords, travel_mode=TravelMode.DRIVE.value)
                drive_mins = route.duration_minutes if route else 15
                dist_km = route.distance_km if route else 2.5

                msg = (
                    f"Route Analysis: Traveling from '{title_a}' to '{title_b}' takes approximately "
                    f"{drive_mins} minutes ({dist_km:.1f} km drive) under normal traffic conditions.\n\n"
                    "Make sure to account for parking and transit buffers between these scheduled stops."
                )
            else:
                msg = (
                    f"To estimate travel time accurately for '{trip_title}', please add at least two activities "
                    "with locations to your itinerary."
                )

            return AssistantEngineResult(
                message=msg,
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.ESTIMATE_TRAVEL_TIME,
                    AssistantActionType.CHECK_ROUTE_BETWEEN_ACTIVITIES,
                ),
            )


        # 3. Proactive Intelligence — Budget Risks Check
        if (
            "budget risk" in msg_lower
            or "spending risk" in msg_lower
            or "over budget" in msg_lower
            or "budget alert" in msg_lower
            or "check_budget_risks" in msg_lower
        ):
            warnings = context.get("proactive_warnings", [])
            budget_warnings = [w for w in warnings if w.get("category") == "budget"]
            if budget_warnings:
                details = "\n".join(f"- ⚠️ {w.get('message')}" for w in budget_warnings)
                msg = f"I identified the following budget risks for '{trip_title}':\n\n{details}\n\nConsider reallocating category limits or trimming upcoming optional expenses."
            else:
                msg = f"Budget health check complete: Your spending is within healthy limits for '{trip_title}'."

            return AssistantEngineResult(
                message=msg,
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(
                    AssistantActionType.READ_BUDGET,
                    AssistantActionType.CHECK_BUDGET_RISKS,
                ),
            )

        # 4. Proactive Intelligence — General Issues / Audit
        if (
            "any issue" in msg_lower
            or "any problem" in msg_lower
            or "warnings" in msg_lower
            or "check my trip" in msg_lower
            or "audit" in msg_lower
        ):
            warnings = context.get("proactive_warnings", [])
            if warnings:
                details = "\n".join(f"- ⚠️ {w.get('message')}" for w in warnings)
                msg = f"Here is my proactive travel intelligence analysis for '{trip_title}':\n\n{details}\n\nLet me know if you would like me to propose adjustments to resolve these issues."
            else:
                msg = f"Great news! I scanned '{trip_title}' and found no itinerary conflicts, travel feasibility issues, or budget risks."

            return AssistantEngineResult(
                message=msg,
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(
                    AssistantActionType.CHECK_ITINERARY_CONFLICTS,
                    AssistantActionType.CHECK_TRAVEL_FEASIBILITY,
                    AssistantActionType.CHECK_BUDGET_RISKS,
                ),
            )

        # 5. Budget Expense Addition
        if (
            ("log" in msg_lower and "expense" in msg_lower)
            or ("add" in msg_lower and ("expense" in msg_lower or "spent" in msg_lower or "$" in user_message))
            or ("spent" in msg_lower and ("$" in user_message or "dollar" in msg_lower or "usd" in msg_lower))
        ):
            # Extract amount if present
            amount = "45.00"
            amount_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", user_message)
            if amount_match:
                amount = amount_match.group(1)

            expense_title = "Dinner & Refreshments"
            if "lunch" in msg_lower:
                expense_title = "Local Lunch"
            elif "coffee" in msg_lower or "cafe" in msg_lower:
                expense_title = "Cafe & Snacks"
            elif "taxi" in msg_lower or "train" in msg_lower or "transport" in msg_lower:
                expense_title = "Local Transit"
            elif "ticket" in msg_lower or "museum" in msg_lower:
                expense_title = "Admission Tickets"

            # Match category
            cat_id = None
            for c in categories:
                if "food" in c.get("name", "").lower() or "dining" in c.get("name", "").lower():
                    cat_id = c.get("category_id")
                    break
            if not cat_id and categories:
                cat_id = categories[0].get("category_id")

            curr = budget.get("currency", "USD")
            return AssistantEngineResult(
                message=f"I've prepared a proposal to log an expense of {amount} {curr} for '{expense_title}'. Would you like me to record this in your trip budget?",
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_ADDING_EXPENSE,
                    summary=f"Log expense of {amount} {curr} for '{expense_title}'",
                    description=f"Records an expense of {amount} {curr} under category '{expense_title}'.",
                    payload={
                        "title": expense_title,
                        "amount": amount,
                        "category_id": cat_id,
                        "expense_type": "restaurant" if any(w in msg_lower for w in ["dinner", "lunch", "food", "ramen", "coffee", "restaurant"]) else "other",
                        "currency": curr,
                        "description": "Logged via Travix AI assistant conversation.",
                    },
                ),
                tools_used=(AssistantActionType.READ_BUDGET, AssistantActionType.PROPOSE_ADDING_EXPENSE),
            )

        # 2. Budget Limit Update
        if (
            ("increase" in msg_lower or "update" in msg_lower or "set" in msg_lower)
            and ("budget" in msg_lower or "limit" in msg_lower)
        ):
            new_limit = "4000.00"
            amount_match = re.search(r"\$?(\d+(?:,\d{3})*(?:\.\d{1,2})?)", user_message)
            if amount_match:
                cleaned = amount_match.group(1).replace(",", "")
                new_limit = cleaned

            curr = budget.get("currency", "USD")
            return AssistantEngineResult(
                message=f"I've prepared a proposal to update your trip budget limit to {new_limit} {curr}. Would you like me to apply this update?",
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_UPDATING_BUDGET_LIMIT,
                    summary=f"Update budget limit to {new_limit} {curr}",
                    description=f"Adjusts overall spending limit for {trip_title} to {new_limit} {curr}.",
                    payload={
                        "new_limit": new_limit,
                        "limit_amount": new_limit,
                        "currency": curr,
                    },
                ),
                tools_used=(AssistantActionType.READ_BUDGET, AssistantActionType.PROPOSE_UPDATING_BUDGET_LIMIT),
            )

        # 3. Read Expenses
        if "expenses" in msg_lower or "recent spend" in msg_lower or "list expense" in msg_lower:
            recent_exps = budget.get("recent_expenses", [])
            curr = budget.get("currency", "USD")
            if not recent_exps:
                return AssistantEngineResult(
                    message=f"You currently have no expenses recorded for {trip_title}.",
                    response_type=AssistantResponseType.INFORMATIONAL,
                    tools_used=(AssistantActionType.READ_EXPENSES,),
                )
            items_str = ", ".join(f"{e.get('title')} ({e.get('amount')} {curr})" for e in recent_exps)
            return AssistantEngineResult(
                message=f"Here are your recent expenses for {trip_title}: {items_str}.",
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(AssistantActionType.READ_EXPENSES,),
            )

        # 4. Media Query
        if "photo" in msg_lower or "media" in msg_lower or "attachment" in msg_lower or "receipt" in msg_lower:
            total_media = media.get("total_items", 0)
            photos = media.get("photos_count", 0)
            receipts = media.get("receipts_count", 0)
            return AssistantEngineResult(
                message=f"You have {total_media} media items attached to {trip_title} ({photos} photos, {receipts} receipts).",
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(AssistantActionType.READ_MEDIA,),
            )

        # 5. Budget Status Question
        if "budget" in msg_lower or "how much" in msg_lower or "spent" in msg_lower:
            total_spent = budget.get("total_spent", 0)
            limit = budget.get("limit") or budget.get("limit_amount", 0)
            curr = budget.get("currency", "USD")
            return AssistantEngineResult(
                message=f"For {trip_title}, your current budget is {total_spent:,.2f} {curr} spent out of {limit:,.2f} {curr}.",
                response_type=AssistantResponseType.INFORMATIONAL,
                tools_used=(AssistantActionType.READ_BUDGET,),
            )

        # 6. Grounded Place / Restaurant Search (e.g. "Find a good vegetarian restaurant near Day 2", "Find dinner near Day 1", "Search places")
        if (
            (
                "find" in msg_lower or "search" in msg_lower or "restaurant" in msg_lower or "venue" in msg_lower or "place" in msg_lower
            )
            and any(w in msg_lower for w in ["near", "restaurant", "food", "dinner", "lunch", "cafe", "coffee", "vegetarian", "museum", "attraction", "place"])
            and not any(w in msg_lower for w in ["replace", "swap", "substitute", "rain", "storm", "weather", "too busy", "more relaxed", "move lunch"])
        ):
            # Determine Day context
            day_number = 1
            if "day 2" in msg_lower:
                day_number = 2
            elif "day 3" in msg_lower:
                day_number = 3

            target_day_id = None
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    break
            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            # Query PlacesProvider
            query = "restaurant"
            if "vegetarian" in msg_lower:
                query = "vegetarian restaurant"
            elif "coffee" in msg_lower or "cafe" in msg_lower:
                query = "coffee"
            elif "museum" in msg_lower:
                query = "museum"
            elif "dinner" in msg_lower or "food" in msg_lower:
                query = "restaurant"
            elif "colosseum" in msg_lower:
                query = "Colosseum"
            elif "eiffel" in msg_lower:
                query = "Eiffel Tower"
            elif "tokyo" in msg_lower:
                query = "Tokyo Tower"

            # Check if testing unverified/non-existent query
            if "atlantis" in msg_lower or "nonexistent" in msg_lower or "fictional" in msg_lower:
                return AssistantEngineResult(
                    message=f"I searched our verified places database for '{user_message}', but found no verified real-world places. Please refine your search.",
                    response_type=AssistantResponseType.INFORMATIONAL,
                    tools_used=(AssistantActionType.SEARCH_PLACES,),
                )

            candidates = await self._places_provider.text_search(query)
            if candidates:
                verified = candidates[0]
                return AssistantEngineResult(
                    message=(
                        f"I found a verified place for Day {day_number}: **{verified.name}** "
                        f"({verified.rating or 4.5}⭐) located at {verified.formatted_address}. "
                        f"Would you like me to add it to your Day {day_number} itinerary?"
                    ),
                    response_type=AssistantResponseType.PROPOSED_MUTATION,
                    proposed_action=ProposedActionData(
                        action_type=AssistantActionType.PROPOSE_ADDING_PLACE,
                        summary=f"Add {verified.name} to Day {day_number}",
                        description=f"Adds verified venue {verified.name} ({verified.formatted_address}) to Day {day_number}.",
                        payload={
                            "day_id": target_day_id,
                            "day_number": day_number,
                            "title": verified.name,
                            "place_name": verified.name,
                            "provider_place_id": verified.provider_place_id,
                            "formatted_address": verified.formatted_address,
                            "latitude": verified.latitude,
                            "longitude": verified.longitude,
                            "rating": verified.rating,
                            "item_type": "restaurant" if "restaurant" in verified.types else "activity",
                            "description": f"Verified venue at {verified.formatted_address}.",
                            "start_time": "19:00",
                            "end_time": "20:30",
                            "is_verified": True,
                        },
                    ),
                    tools_used=(
                        AssistantActionType.SEARCH_PLACES,
                        AssistantActionType.PROPOSE_ADDING_PLACE,
                    ),
                )
            else:
                return AssistantEngineResult(
                    message=f"I searched for verified places matching '{query}', but no verified results were found.",
                    response_type=AssistantResponseType.INFORMATIONAL,
                    tools_used=(AssistantActionType.SEARCH_PLACES,),
                )

        # 7. Add Activity (General)
        if "add" in msg_lower or "include" in msg_lower:
            day_number = 1
            if "day 2" in msg_lower:
                day_number = 2
            elif "day 3" in msg_lower:
                day_number = 3

            target_day_id = None
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    break
            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            activity_title = "Scenic Evening Walk & Dinner"
            if "dinner" in msg_lower:
                activity_title = "Local Dining Experience"
            elif "museum" in msg_lower:
                activity_title = "Art & History Museum Visit"
            elif "coffee" in msg_lower or "cafe" in msg_lower:
                activity_title = "Artisan Coffee Tasting"

            return AssistantEngineResult(
                message=f"I've prepared a proposal to add '{activity_title}' to Day {day_number}. Would you like me to apply this to your itinerary?",
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_ADDING_ACTIVITY,
                    summary=f"Add '{activity_title}' to Day {day_number}",
                    description=f"Adds a recommended activity '{activity_title}' with estimated duration of 90 minutes.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "title": activity_title,
                        "item_type": "activity",
                        "description": "Recommended by Travix AI assistant based on your trip schedule.",
                        "start_time": "18:30",
                        "end_time": "20:00",
                        "cost": "35.00",
                        "currency": budget.get("currency", "USD"),
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.PROPOSE_ADDING_ACTIVITY,
                ),
            )

        # 8. Sprint 17: Weather-Aware Adaptation ("It's going to rain tomorrow. What should I do?")
        if "rain" in msg_lower or "storm" in msg_lower or "weather" in msg_lower:
            day_number = 2 if "tomorrow" in msg_lower or "day 2" in msg_lower else 1
            target_day_id = None
            outdoor_item_id = None
            outdoor_item_title = "Outdoor Sightseeing Tour"
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    for item in d.get("items", []):
                        outdoor_item_id = item.get("item_id")
                        outdoor_item_title = item.get("title", "Outdoor Sightseeing")
                        break
                    break

            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            indoor_place_name = "Chamundeshwari Art & Heritage Museum"
            return AssistantEngineResult(
                message=(
                    f"⚠️ **Rain Advisory for Day {day_number}**: Rainfall is forecast during your scheduled outdoor hours.\n\n"
                    f"I recommend swapping **{outdoor_item_title}** for a verified indoor alternative: **{indoor_place_name}** "
                    f"(4.6⭐, sheltered exhibits). This keeps your day engaging while staying completely dry."
                ),
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                    summary=f"Replace '{outdoor_item_title}' with indoor '{indoor_place_name}'",
                    description=f"Rain-safe indoor substitution for Day {day_number} outdoor stop.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "old_item_id": outdoor_item_id,
                        "old_title": outdoor_item_title,
                        "title": indoor_place_name,
                        "place_name": indoor_place_name,
                        "item_type": "museum",
                        "description": "Verified indoor cultural museum with sheltered exhibits.",
                        "start_time": "14:30",
                        "end_time": "16:30",
                        "cost": "15.00",
                        "currency": budget.get("currency", "USD"),
                        "rationale": f"Severe rain forecast for Day {day_number}. Replaces outdoor stop with verified indoor venue.",
                        "travel_time_impact": "Direct 10-minute sheltered transit.",
                        "budget_impact": "Matches existing activity budget.",
                        "is_weather_adjustment": True,
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.CHECK_WEATHER_FORECAST,
                    AssistantActionType.SEARCH_PLACES,
                    AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                ),
            )

        # 9. Sprint 17: Replace Activity With Nearby Verified Place ("Replace palace with something nearby")
        if "replace" in msg_lower or "swap" in msg_lower or "substitute" in msg_lower:
            day_number = 1
            if "day 2" in msg_lower or "tomorrow" in msg_lower:
                day_number = 2
            elif "day 3" in msg_lower:
                day_number = 3

            target_day_id = None
            old_item_id = None
            old_item_title = "Mysore Palace"
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    for item in d.get("items", []):
                        if any(w in item.get("title", "").lower() for w in ["palace", "museum", "temple", "tour", "visit"]):
                            old_item_id = item.get("item_id")
                            old_item_title = item.get("title")
                            break
                        if not old_item_id:
                            old_item_id = item.get("item_id")
                            old_item_title = item.get("title")
                    break

            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            replacement_name = "Jaganmohan Palace Art Gallery"
            return AssistantEngineResult(
                message=(
                    f"I found a verified cultural venue located just 1.2 km from your current route: **{replacement_name}** (4.7⭐).\n\n"
                    f"Replacing **{old_item_title}** with **{replacement_name}** cuts your transit by 15 minutes and offers a quieter, less crowded experience. "
                    f"Would you like me to update your Day {day_number} plan?"
                ),
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                    summary=f"Replace '{old_item_title}' with nearby '{replacement_name}'",
                    description=f"Nearby verified alternative located 1.2 km away on Day {day_number}.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "old_item_id": old_item_id,
                        "old_title": old_item_title,
                        "title": replacement_name,
                        "place_name": replacement_name,
                        "item_type": "sightseeing",
                        "description": "Verified historic art gallery with royal artifacts and tranquil gardens.",
                        "start_time": "11:00",
                        "end_time": "13:00",
                        "cost": "20.00",
                        "currency": budget.get("currency", "USD"),
                        "rationale": f"Replaces crowded {old_item_title} with nearby verified gallery.",
                        "travel_time_impact": "Saves 15 minutes of transit time.",
                        "budget_impact": "Reduces entry cost by ₹150.",
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.SEARCH_PLACES,
                    AssistantActionType.ESTIMATE_TRAVEL_TIME,
                    AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                ),
            )

        # 10. Sprint 17: Spend Less / Budget Optimization ("Can we spend less tomorrow?")
        if "spend less" in msg_lower or "cheaper" in msg_lower or "budget friendly" in msg_lower or "save money" in msg_lower:
            day_number = 2 if "tomorrow" in msg_lower or "day 2" in msg_lower else 1
            target_day_id = None
            old_item_id = None
            old_item_title = "Fine Dining Experience"
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    for item in d.get("items", []):
                        old_item_id = item.get("item_id")
                        old_item_title = item.get("title")
                        break
                    break

            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            budget_saving_activity = "Historic Heritage Walk & Local Street Food"
            return AssistantEngineResult(
                message=(
                    f"To optimize spending for Day {day_number}, I recommend replacing premium scheduled stops with **{budget_saving_activity}** (Free / low-cost).\n\n"
                    f"This reduces your estimated daily expense from ₹3,500 to ₹800 without sacrificing local authenticity."
                ),
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                    summary=f"Replace '{old_item_title}' with budget-friendly '{budget_saving_activity}'",
                    description=f"Reduces Day {day_number} expenses while preserving cultural immersion.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "old_item_id": old_item_id,
                        "old_title": old_item_title,
                        "title": budget_saving_activity,
                        "place_name": budget_saving_activity,
                        "item_type": "walking_tour",
                        "description": "Guided self-paced heritage walk through historic market streets.",
                        "start_time": "17:00",
                        "end_time": "18:45",
                        "cost": "10.00",
                        "currency": budget.get("currency", "USD"),
                        "rationale": "Optimizes itinerary costs for Day 2 to preserve trip budget limits.",
                        "travel_time_impact": "Pedestrian-friendly central route.",
                        "budget_impact": "Saves approximately ₹2,700.",
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_BUDGET,
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
                ),
            )

        # 11. Sprint 17: Move / Reschedule Activity ("Move lunch closer to the next activity")
        if "move lunch" in msg_lower or "reschedule" in msg_lower or "move activity" in msg_lower or "closer" in msg_lower:
            day_number = 1
            if "day 2" in msg_lower or "tomorrow" in msg_lower:
                day_number = 2
            target_day_id = None
            lunch_item_id = None
            lunch_title = "Traditional South Indian Lunch"
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    for item in d.get("items", []):
                        if "lunch" in item.get("title", "").lower() or "dining" in item.get("title", "").lower():
                            lunch_item_id = item.get("item_id")
                            lunch_title = item.get("title")
                            break
                        if not lunch_item_id:
                            lunch_item_id = item.get("item_id")
                            lunch_title = item.get("title")
                    break

            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            return AssistantEngineResult(
                message=(
                    f"I analyzed your route between lunch and the afternoon activity. Moving **{lunch_title}** to **13:00 - 14:15** "
                    f"eliminates a 45-minute idle transit gap and places you right next to the 14:30 tour.\n\n"
                    f"Would you like me to update this time slot?"
                ),
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_RESCHEDULING_ACTIVITY,
                    summary=f"Reschedule '{lunch_title}' to 13:00 - 14:15",
                    description=f"Adjusts time slot for '{lunch_title}' on Day {day_number} to optimize route flow.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "item_id": lunch_item_id,
                        "title": lunch_title,
                        "start_time": "13:00",
                        "end_time": "14:15",
                        "rationale": "Aligns lunch finish time directly with subsequent afternoon stop.",
                        "travel_time_impact": "Reduces transit wait time by 45 minutes.",
                        "budget_impact": "No budget change.",
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.ESTIMATE_TRAVEL_TIME,
                    AssistantActionType.PROPOSE_RESCHEDULING_ACTIVITY,
                ),
            )

        # 12. Sprint 17: Pacing / Relaxing Busy Day ("Day 2 is too busy. Make it more relaxed.")
        if "too busy" in msg_lower or "more relaxed" in msg_lower or "less tiring" in msg_lower or "relax" in msg_lower:
            day_number = 2 if "day 2" in msg_lower or "tomorrow" in msg_lower else 1
            target_day_id = None
            for d in days:
                if d.get("day_number") == day_number:
                    target_day_id = d.get("day_id")
                    break

            if not target_day_id and days:
                target_day_id = days[0].get("day_id")
                day_number = days[0].get("day_number", 1)

            return AssistantEngineResult(
                message=(
                    f"Day {day_number} currently contains multiple tightly scheduled activities. I recommend restructuring the day with a **2-hour afternoon relaxation window** and shifting your evening stroll to golden hour.\n\n"
                    f"This reduces rushed transit and lets you explore at a comfortable pace."
                ),
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_ITINERARY_CHANGE,
                    summary=f"Optimize Day {day_number} for relaxed pacing",
                    description=f"Adjusts Day {day_number} pacing with scheduled afternoon leisure buffers.",
                    payload={
                        "day_id": target_day_id,
                        "day_number": day_number,
                        "title": "Relaxed Heritage & Cultural Immersion",
                        "rationale": "Introduces a 2-hour afternoon leisure window to eliminate travel fatigue.",
                        "travel_time_impact": "Eliminates back-to-back transit rush.",
                        "budget_impact": "No cost impact.",
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.PROPOSE_ITINERARY_CHANGE,
                ),
            )

        # 13. Remove Activity / Free Time ("Remove the last activity and give me more free time.")
        if "remove" in msg_lower or "delete" in msg_lower or "drop" in msg_lower or "free time" in msg_lower:
            target_item_id = None
            target_item_title = "Scheduled Evening Activity"
            target_day_number = 1

            for d in reversed(days):
                items = d.get("items", [])
                if items:
                    last_item = items[-1]
                    target_item_id = last_item.get("item_id")
                    target_item_title = last_item.get("title", "Activity")
                    target_day_number = d.get("day_number", 1)
                    break

            return AssistantEngineResult(
                message=f"I've prepared a proposal to remove **{target_item_title}** from Day {target_day_number}. This gives you 2.5 hours of unhurried free time in the evening. Would you like me to proceed?",
                response_type=AssistantResponseType.PROPOSED_MUTATION,
                proposed_action=ProposedActionData(
                    action_type=AssistantActionType.PROPOSE_REMOVING_ACTIVITY,
                    summary=f"Remove '{target_item_title}' from Day {target_day_number}",
                    description=f"Removes the last item '{target_item_title}' to create 2.5h of flexible leisure time.",
                    payload={
                        "item_id": target_item_id,
                        "item_title": target_item_title,
                        "day_number": target_day_number,
                        "rationale": "Frees up evening schedule for spontaneous dining and relaxation.",
                        "travel_time_impact": "Eliminates late-night transit return.",
                        "budget_impact": "Saves any admission or activity expenses.",
                    },
                ),
                tools_used=(
                    AssistantActionType.READ_ITINERARY,
                    AssistantActionType.PROPOSE_REMOVING_ACTIVITY,
                ),
            )

        # 14. Recommendation
        if "recommend" in msg_lower or "suggest" in msg_lower or "where" in msg_lower or "what" in msg_lower:
            return AssistantEngineResult(
                message=f"Based on your itinerary for {trip_title}, I recommend exploring local specialty markets and artisan districts in the late afternoon when pedestrian foot traffic is vibrant.",
                response_type=AssistantResponseType.RECOMMENDATION,
                tools_used=(AssistantActionType.READ_TRIP, AssistantActionType.READ_ITINERARY),
            )

        # 15. Default Informational Response
        return AssistantEngineResult(
            message=f"I am your Travix AI assistant for '{trip_title}'. I can help you inspect your itinerary ({len(days)} days planned), search verified real-world places, monitor expenses, or propose schedule optimizations. How can I assist?",
            response_type=AssistantResponseType.INFORMATIONAL,
            tools_used=(AssistantActionType.READ_TRIP,),
        )

