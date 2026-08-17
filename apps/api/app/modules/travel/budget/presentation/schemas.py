"""Budget presentation schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Standard success data envelope wrapper."""

    data: T
    model_config = ConfigDict(populate_by_name=True)


class BudgetCreateRequest(BaseModel):
    """Request schema for creating a trip budget."""

    limit_amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        description="Budget total limit, must be positive.",
        examples=[Decimal("2500.00")],
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="3-letter ISO currency code.",
        examples=["USD"],
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if not v.isalpha():
            raise ValueError("Currency must only contain alphabetic characters.")
        return v.upper()

    model_config = ConfigDict(extra="forbid")


class BudgetUpdateRequest(BaseModel):
    """Request schema for updating budget limit or status."""

    limit_amount: Decimal | None = Field(
        None,
        gt=Decimal("0.00"),
        description="Updated budget limit. Must match existing currency.",
    )
    status: Literal["active", "closed"] | None = Field(
        None,
        description="Target status of the budget.",
    )

    model_config = ConfigDict(extra="forbid")


class ExpenseCreateRequest(BaseModel):
    """Request schema for adding a new expense."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Short description of the spend.",
        examples=["Museum entry tickets"],
    )
    amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        description="Positive numeric amount spent.",
        examples=[Decimal("45.00")],
    )
    category_id: str = Field(
        ...,
        description="UUID of the budget category.",
        examples=["d3b07384-d113-4956-a547-5fe98c47f433"],
    )
    expense_type: Literal["activity", "transport", "lodging", "restaurant", "other"] = Field(
        ...,
        description="Predefined category group for classification.",
    )
    expense_date: date = Field(
        ...,
        description="Date the expense was incurred.",
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Optional additional details.",
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty after stripping whitespace.")
        return stripped

    model_config = ConfigDict(extra="forbid")


class ExpenseUpdateRequest(BaseModel):
    """Request schema for updating an existing expense."""

    title: str | None = Field(
        None,
        min_length=1,
        max_length=100,
    )
    amount: Decimal | None = Field(
        None,
        gt=Decimal("0.00"),
    )
    category_id: str | None = None
    expense_type: Literal["activity", "transport", "lodging", "restaurant", "other"] | None = None
    expense_date: date | None = None
    description: str | None = Field(None, max_length=500)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty after stripping whitespace.")
        return stripped

    model_config = ConfigDict(extra="forbid")


class CategoryResponse(BaseModel):
    """Response schema representing a budget category."""

    id: str = Field(alias="category_id")
    name: str
    description: str | None
    icon: str | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BudgetResponse(BaseModel):
    """Response schema representing a TripBudget."""

    id: str = Field(alias="budget_id")
    trip_id: str
    owner_id: str
    limit: Decimal
    currency: str
    status: str
    total_spent: Decimal
    remaining: Decimal
    spent_percentage: Decimal
    categories: list[CategoryResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExpenseResponse(BaseModel):
    """Response schema representing an Expense entry."""

    id: str = Field(alias="expense_id")
    title: str
    amount: Decimal
    currency: str
    category_id: str
    expense_type: str
    description: str | None
    expense_date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExpenseListResponse(BaseModel):
    """Opaque cursor-paginated page of expenses response."""

    items: tuple[ExpenseResponse, ...]
    next_cursor: str | None
    has_more: bool
    limit: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BudgetSummaryResponse(BaseModel):
    """Complete budget details with structural breakdowns."""

    budget: BudgetResponse
    category_breakdowns: dict[str, Decimal]
    type_breakdowns: dict[str, Decimal]

    model_config = ConfigDict(from_attributes=True)
