"""Real-Time Domain Enums."""

from __future__ import annotations

from enum import Enum


class RealtimeEventType(str, Enum):
    """Types of real-time events broadcast over WebSocket."""

    # Presence
    PRESENCE_JOINED = "presence.joined"
    PRESENCE_LEFT = "presence.left"
    PRESENCE_SYNC = "presence.sync"

    # Itinerary
    ITINERARY_DAY_CREATED = "itinerary.day_created"
    ITINERARY_DAY_UPDATED = "itinerary.day_updated"
    ITINERARY_DAY_DELETED = "itinerary.day_deleted"
    ITINERARY_ITEM_CREATED = "itinerary.item_created"
    ITINERARY_ITEM_UPDATED = "itinerary.item_updated"
    ITINERARY_ITEM_DELETED = "itinerary.item_deleted"

    # Budget
    BUDGET_UPDATED = "budget.updated"
    BUDGET_LIMIT_UPDATED = "budget.limit_updated"
    BUDGET_EXPENSE_CREATED = "budget.expense_created"
    BUDGET_EXPENSE_UPDATED = "budget.expense_updated"
    BUDGET_EXPENSE_DELETED = "budget.expense_deleted"
    BUDGET_CATEGORY_CREATED = "budget.category_created"
    BUDGET_CATEGORY_UPDATED = "budget.category_updated"
    BUDGET_CATEGORY_DELETED = "budget.category_deleted"

    # Trip
    TRIP_UPDATED = "trip.updated"
    TRIP_STATUS_UPDATED = "trip.status_updated"

    # Collaboration
    COLLABORATION_MEMBER_ADDED = "collaboration.member_added"
    COLLABORATION_MEMBER_UPDATED = "collaboration.member_updated"
    COLLABORATION_MEMBER_REMOVED = "collaboration.member_removed"
    COLLABORATION_ROLE_CHANGED = "collaboration.role_changed"

    # Synchronization & Concurrency
    SYNC_CONFLICT = "sync.conflict"


class EntityType(str, Enum):
    """Type of entity affected by a real-time event."""

    TRIP = "trip"
    ITINERARY = "itinerary"
    DAY = "day"
    ITEM = "item"
    BUDGET = "budget"
    EXPENSE = "expense"
    CATEGORY = "category"
    MEMBER = "member"
    PRESENCE = "presence"


class EntityActionType(str, Enum):
    """Action performed on the entity."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    JOINED = "joined"
    LEFT = "left"
    SYNC = "sync"
    CONFLICT = "conflict"
