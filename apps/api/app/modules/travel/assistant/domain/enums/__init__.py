"""Assistant Domain Enums."""

from __future__ import annotations

from enum import Enum


class AssistantResponseType(str, Enum):
    """Type of response produced by the AI assistant."""

    INFORMATIONAL = "informational"
    RECOMMENDATION = "recommendation"
    PROPOSED_MUTATION = "proposed_mutation"


class AssistantActionType(str, Enum):
    """Supported safe AI actions."""

    # Reading trip domains
    READ_TRIP = "read_trip"
    READ_ITINERARY = "read_itinerary"
    READ_BUDGET = "read_budget"
    READ_EXPENSES = "read_expenses"
    READ_MEDIA = "read_media"

    # Places / Real-World grounding
    SEARCH_PLACES = "search_places"
    GET_PLACE_DETAILS = "get_place_details"
    FIND_NEARBY_PLACES = "find_nearby_places"

    # Proactive Intelligence & Feasibility (Read-only tools)
    CHECK_ITINERARY_CONFLICTS = "check_itinerary_conflicts"
    CHECK_TRAVEL_FEASIBILITY = "check_travel_feasibility"
    CHECK_BUDGET_RISKS = "check_budget_risks"
    CHECK_WEATHER_FORECAST = "check_weather_forecast"
    ESTIMATE_TRAVEL_TIME = "estimate_travel_time"
    CHECK_ROUTE_BETWEEN_ACTIVITIES = "check_route_between_activities"

    # Itinerary & Place mutations (requires user confirmation)
    PROPOSE_ITINERARY_CHANGE = "propose_itinerary_change"
    PROPOSE_ADDING_ACTIVITY = "propose_adding_activity"
    PROPOSE_ADDING_PLACE = "propose_adding_place"
    PROPOSE_REMOVING_ACTIVITY = "propose_removing_activity"
    PROPOSE_RESCHEDULING_ACTIVITY = "propose_rescheduling_activity"
    PROPOSE_REPLACING_ACTIVITY = "propose_replacing_activity"
    PROPOSE_REORDERING_ACTIVITIES = "propose_reordering_activities"

    # Budget mutations (requires user confirmation)
    PROPOSE_ADDING_EXPENSE = "propose_adding_expense"
    PROPOSE_UPDATING_BUDGET_LIMIT = "propose_updating_budget_limit"
    PROPOSE_ADJUSTING_BUDGET = "propose_adjusting_budget"


class WarningCategory(str, Enum):
    """Category of travel warning."""

    TIMING = "timing"
    DISTANCE = "distance"
    BUDGET = "budget"
    FEASIBILITY = "feasibility"
    WEATHER = "weather"


class WarningSeverity(str, Enum):
    """Severity level of travel warning."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"



class ActionStatus(str, Enum):
    """Status of a proposed action."""

    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
