"""Pydantic v2 schemas for the Travel Planning presentation layer."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.modules.travel.planning.application.dtos import ProposalListPage, ProposalSummary
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)

T = TypeVar("T")


class DataEnvelope[T](BaseModel):
    """Standard success data envelope wrapper."""

    model_config = ConfigDict(populate_by_name=True)
    data: T


# ──────────────────────────────────────────────────────────────────────────── #
# Request Schemas                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class ProposalCreateRequest(BaseModel):
    """Request schema for creating a new TripProposal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    destination: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Target city, region, or country for the plan.",
            examples=["Lisbon"],
        ),
    ]

    duration_days: Annotated[
        int,
        Field(
            ge=1,
            le=30,
            description="Number of days to plan (1-30).",
            examples=[3],
        ),
    ]

    budget_level: Annotated[
        str,
        Field(
            description="Budget level for recommendations. One of: budget, mid_range, luxury.",
            examples=["mid_range"],
        ),
    ]

    interests: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="List of user interests (e.g. food, history, outdoors).",
            examples=[["food", "history"]],
        ),
    ]

    travel_style: Annotated[
        str,
        Field(
            description="Travel style preference. One of: relaxed, balanced, active.",
            examples=["balanced"],
        ),
    ]

    special_requirements: Annotated[
        str,
        Field(
            default="",
            max_length=1000,
            description="Accessibility requirements, dietary needs, or other special constraints.",
            examples=["Vegetarian food options requested."],
        ),
    ] = ""


# ──────────────────────────────────────────────────────────────────────────── #
# Response Schemas                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


class ProposalPreferencesSchema(BaseModel):
    """Response sub-schema for planning preferences."""

    model_config = ConfigDict(populate_by_name=True)

    destination: str
    duration_days: int
    budget_level: str
    interests: list[str]
    travel_style: str
    special_requirements: str

    @classmethod
    def from_vo(cls, vo: PlanningPreferences) -> ProposalPreferencesSchema:
        return cls(
            destination=vo.destination,
            duration_days=vo.duration_days,
            budget_level=vo.budget_level,
            interests=list(vo.interests),
            travel_style=vo.travel_style,
            special_requirements=vo.special_requirements,
        )


class ProposedActivityResponse(BaseModel):
    """Response schema for a single proposed activity."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str
    category: str
    duration_minutes: int
    estimated_cost: str | None


class ProposedDayResponse(BaseModel):
    """Response schema for a proposed travel day."""

    model_config = ConfigDict(populate_by_name=True)

    day_number: int
    title: str
    description: str
    activities: list[ProposedActivityResponse]


class PlanningResultResponse(BaseModel):
    """Response schema for generated AI planning results."""

    model_config = ConfigDict(populate_by_name=True)

    summary: str
    days: list[ProposedDayResponse]
    estimated_total_cost: str | None
    generated_at: datetime

    @classmethod
    def from_vo(cls, vo: PlanningResult | None) -> PlanningResultResponse | None:
        if vo is None:
            return None
        days = []
        for d in vo.days:
            acts = []
            for a in d.activities:
                acts.append(
                    ProposedActivityResponse(
                        title=a.title,
                        description=a.description,
                        category=a.category,
                        duration_minutes=a.duration_minutes,
                        estimated_cost=a.estimated_cost,
                    )
                )
            days.append(
                ProposedDayResponse(
                    day_number=d.day_number,
                    title=d.title,
                    description=d.description,
                    activities=acts,
                )
            )
        return cls(
            summary=vo.summary,
            days=days,
            estimated_total_cost=vo.estimated_total_cost,
            generated_at=vo.generated_at,
        )


class ProposalResponse(BaseModel):
    """Response schema representing a single travel proposal."""

    model_config = ConfigDict(populate_by_name=True)

    proposal_id: str
    trip_id: str
    owner_id: str
    preferences: ProposalPreferencesSchema
    status: str
    result: PlanningResultResponse | None
    failure_reason: str | None
    expires_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_dto(cls, dto: ProposalSummary) -> ProposalResponse:
        return cls(
            proposal_id=str(dto.proposal_id),
            trip_id=str(dto.trip_id),
            owner_id=str(dto.owner_id),
            preferences=ProposalPreferencesSchema.from_vo(dto.preferences),
            status=dto.status.value,
            result=PlanningResultResponse.from_vo(dto.result),
            failure_reason=dto.failure_reason,
            expires_at=dto.expires_at,
            version=dto.version,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            deleted_at=dto.deleted_at,
        )


class ProposalPageResponse(BaseModel):
    """Paginated collection response for proposals."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ProposalResponse]
    next_cursor: str | None
    has_more: bool
    limit: int

    @classmethod
    def from_page_dto(cls, dto: ProposalListPage) -> ProposalPageResponse:
        return cls(
            items=[ProposalResponse.from_dto(item) for item in dto.items],
            next_cursor=dto.next_cursor,
            has_more=dto.has_more,
            limit=dto.limit,
        )
