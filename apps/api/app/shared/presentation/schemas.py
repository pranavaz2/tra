"""
Travix AI — Shared Presentation Schemas

Base Pydantic models used by all feature modules for API request and response
bodies. Centralising base configuration here ensures that every schema in the
codebase inherits the same Pydantic settings without repetition.

Design decisions:
  - from_attributes=True on BaseSchema: allows constructing a schema directly
    from a SQLAlchemy ORM model or any object with matching attributes.
    This avoids writing `.model_validate(orm_obj.__dict__)` everywhere.
  - TimestampedSchema: adds created_at / updated_at to any response model
    whose underlying entity tracks these fields (every entity per CLAUDE.md).
  - IDSchema: a mixin for the common `id: UUID` field on response models.
    Placed here so modules do not define it in four different ways.
  - All schemas use Pydantic v2 ConfigDict — no `class Config` blocks.

Usage:
    from app.shared.presentation.schemas import BaseSchema, TimestampedSchema

    class TripResponse(TimestampedSchema):
        id: UUID
        title: str
        status: TripStatus
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    Root base class for all Travix API schemas.

    from_attributes=True: Pydantic can construct this from ORM model instances
    (SQLAlchemy model attributes are read by name).

    populate_by_name=True: allows both alias and field name to be used when
    constructing the model from dict input (useful for camelCase aliases).
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class IDSchema(BaseSchema):
    """Mixin schema for resources that expose a UUID primary key."""

    id: UUID


class TimestampedSchema(IDSchema):
    """
    Mixin schema for resources that expose audit timestamps.

    Every user-facing entity in Travix has created_at and updated_at columns
    (CLAUDE.md §10). This schema makes them available on all response models
    without duplication.
    """

    created_at: datetime
    updated_at: datetime


class EmptyResponse(BaseSchema):
    """
    Response body for operations that return no meaningful payload.

    Use instead of returning an empty dict or None from endpoints.
    The status code carries the semantic meaning (204 No Content, 200 OK).

    Example:
        @router.delete("/trips/{trip_id}", status_code=204)
        async def delete_trip(...) -> EmptyResponse:
            await service.delete(trip_id)
            return EmptyResponse()
    """


class MessageResponse(BaseSchema):
    """
    Response body for simple acknowledgement messages.

    Use for operations where a human-readable confirmation is appropriate,
    such as email sends, password resets, or async job submissions.

    Example:
        return MessageResponse(message="Password reset email sent.")
    """

    message: str
