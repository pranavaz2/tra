"""Activity domain enums."""

from __future__ import annotations

from enum import StrEnum


class ActivityAction(StrEnum):
    """Categorized action types recorded in trip activity feeds."""

    # Trip lifecycle
    TRIP_CREATED = "trip_created"
    TRIP_UPDATED = "trip_updated"
    TRIP_STATUS_CHANGED = "trip_status_changed"
    TRIP_DELETED = "trip_deleted"

    # Itinerary
    DAY_ADDED = "day_added"
    DAY_UPDATED = "day_updated"
    DAY_REMOVED = "day_removed"
    ITEM_ADDED = "item_added"
    ITEM_UPDATED = "item_updated"
    ITEM_REMOVED = "item_removed"

    # Budget & Expenses
    BUDGET_CREATED = "budget_created"
    BUDGET_LIMIT_UPDATED = "budget_limit_updated"
    EXPENSE_ADDED = "expense_added"
    EXPENSE_UPDATED = "expense_updated"
    EXPENSE_DELETED = "expense_deleted"

    # Collaboration
    MEMBER_INVITED = "member_invited"
    MEMBER_JOINED = "member_joined"
    MEMBER_REMOVED = "member_removed"
    ROLE_CHANGED = "role_changed"

    # AI & Intelligence
    PROPOSAL_ACCEPTED = "proposal_accepted"
