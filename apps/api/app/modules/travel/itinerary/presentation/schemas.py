"""Pydantic v2 schemas for the Itinerary API."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, condecimal

from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Standard success data envelope wrapper."""

    model_config = ConfigDict(populate_by_name=True)
    data: T


# ──────────────────────────────────────────────────────────────────────────── #
# Request Schemas                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class ItineraryDayCreateRequest(BaseModel):
    """Request body schema for adding a day to an itinerary."""

    model_config = ConfigDict(str_strip_whitespace=True)

    day_number: Annotated[
        int,
        Field(
            ge=1,
            description="The sequential day index (1-based). Must be unique within the itinerary.",
            examples=[1],
        ),
    ]

    title: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Optional descriptive title for the day.",
            examples=["Exploring Downtown London"],
        ),
    ] = None

    date: Annotated[
        dt.date | None,
        Field(
            default=None,
            description="Optional specific calendar date for this day.",
            examples=["2027-06-01"],
        ),
    ] = None


class ItineraryDayUpdateRequest(BaseModel):
    """Request body schema for updating an itinerary day."""

    model_config = ConfigDict(str_strip_whitespace=True)

    day_number: Annotated[
        int,
        Field(
            ge=1,
            description="The updated day number.",
            examples=[1],
        ),
    ]

    title: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Updated day title.",
            examples=["Westminster Walking Tour"],
        ),
    ] = None

    date: Annotated[
        dt.date | None,
        Field(
            default=None,
            description="Updated day calendar date.",
            examples=["2027-06-02"],
        ),
    ] = None


class ItineraryItemCreateRequest(BaseModel):
    """Request body schema for adding an activity or segment to a day."""

    model_config = ConfigDict(str_strip_whitespace=True)

    day_id: Annotated[
        UUID,
        Field(
            description="The parent day ID.",
            examples=["e5f67890-abcd-ef12-3456-7890abcdef12"],
        ),
    ]

    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Itinerary item title (1-100 characters).",
            examples=["Visit Tower Bridge"],
        ),
    ]

    item_type: Annotated[
        ItineraryItemType,
        Field(
            description="Category: activity | transport | lodging | restaurant",
            examples=["activity"],
        ),
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            description="Notes, links, or instructions.",
            examples=["Pre-booked fast track tickets required."],
        ),
    ] = None

    start_time: Annotated[
        dt.time | None,
        Field(
            default=None,
            description="Start time (HH:MM:SS or HH:MM).",
            examples=["09:30:00"],
        ),
    ] = None

    end_time: Annotated[
        dt.time | None,
        Field(
            default=None,
            description="End time.",
            examples=["11:00:00"],
        ),
    ] = None

    location_id: Annotated[
        UUID | None,
        Field(
            default=None,
            description="Optional location ID from locations module catalog.",
            examples=["b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b"],
        ),
    ] = None

    cost: condecimal(ge=Decimal("0"), max_digits=10, decimal_places=2) | None = Field(
        default=None,
        description="Estimated cost of the item.",
        examples=[25.50],
    )

    currency: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=3,
            description="Three-letter currency code (ISO 4217).",
            examples=["GBP"],
        ),
    ] = None


class ItineraryItemUpdateRequest(BaseModel):
    """Request body schema for updating an itinerary item."""

    model_config = ConfigDict(str_strip_whitespace=True)

    day_id: Annotated[
        UUID | None,
        Field(
            default=None,
            description="Optional day ID to move the item to a different day.",
            examples=["e5f67890-abcd-ef12-3456-7890abcdef12"],
        ),
    ] = None

    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Updated item title.",
            examples=["Visit Tower Bridge & Exhibition"],
        ),
    ]

    item_type: Annotated[
        ItineraryItemType,
        Field(
            description="Category.",
            examples=["activity"],
        ),
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            description="Updated description.",
            examples=["Bring printed tickets."],
        ),
    ] = None

    start_time: Annotated[
        dt.time | None,
        Field(
            default=None,
            description="Updated start time.",
            examples=["10:00:00"],
        ),
    ] = None

    end_time: Annotated[
        dt.time | None,
        Field(
            default=None,
            description="Updated end time.",
            examples=["12:00:00"],
        ),
    ] = None

    location_id: Annotated[
        UUID | None,
        Field(
            default=None,
            description="Updated location reference ID.",
        ),
    ] = None

    cost: condecimal(ge=Decimal("0"), max_digits=10, decimal_places=2) | None = Field(
        default=None,
        description="Updated cost.",
    )

    currency: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=3,
            description="Updated currency.",
        ),
    ] = None


# ──────────────────────────────────────────────────────────────────────────── #
# Response Schemas                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


class ItineraryItemResponse(BaseModel):
    """Response schema for itinerary items."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(alias="item_id")
    day_id: UUID
    title: str
    item_type: ItineraryItemType
    description: str | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    location_id: UUID | None = None
    cost: Decimal | None = None
    currency: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class ItineraryDayResponse(BaseModel):
    """Response schema for itinerary days."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(alias="day_id")
    day_number: int
    title: str | None = None
    date: dt.date | None = None
    items: list[ItineraryItemResponse]
    created_at: dt.datetime
    updated_at: dt.datetime


class ItineraryResponse(BaseModel):
    """Response schema for the complete itinerary."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(alias="itinerary_id")
    trip_id: UUID
    days: list[ItineraryDayResponse]
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
