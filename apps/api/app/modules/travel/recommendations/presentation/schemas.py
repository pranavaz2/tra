"""Recommendations presentation schemas."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Standard success data envelope wrapper."""

    data: T
    model_config = ConfigDict(populate_by_name=True)


# ──────────────────────────────────────────────────────────────────────────── #
# Request Schemas                                                                #
# ──────────────────────────────────────────────────────────────────────────── #


class UpdatePreferencesRequest(BaseModel):
    """Request schema for updating travel preferences."""

    interests: list[str] = Field(
        ...,
        description="List of user interests.",
    )
    dietary_preferences: list[str] = Field(
        ...,
        description="List of dietary tags.",
    )
    travel_style: str = Field(
        ...,
        description="Preferred travel style (e.g. adventure, culture).",
    )
    travel_pace: str = Field(
        ...,
        description="Preferred pace (slow, medium, fast).",
    )
    budget_tier: str = Field(
        ...,
        description="Budget tier (budget, mid_range, luxury).",
    )

    model_config = ConfigDict(extra="forbid")


# ──────────────────────────────────────────────────────────────────────────── #
# Response Schemas                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


class UserPreferencesResponse(BaseModel):
    """Response schema representing travel preferences."""

    user_id: str
    interests: list[str]
    dietary_preferences: list[str]
    travel_style: str
    travel_pace: str
    budget_tier: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationResponse(BaseModel):
    """Response schema representing a single recommendation."""

    id: str
    title: str
    description: str | None = None
    score: int
    reason: str
    recommendation_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class SimilarTripResponse(BaseModel):
    """Response schema representing a similar trip recommendation."""

    trip_id: str
    title: str
    score: int
    reason: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationsResponse(BaseModel):
    """Response schema wrapping grouped recommendations."""

    destinations: list[RecommendationResponse] = Field(default_factory=list)
    activities: list[RecommendationResponse] = Field(default_factory=list)
    restaurants: list[RecommendationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
