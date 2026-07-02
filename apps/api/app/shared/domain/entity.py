"""
Travix AI — Base Entity

An Entity is an object defined by its IDENTITY, not its attributes.
Two entities with the same ID are the same entity, regardless of their
current attribute values.

Design choices:
  - Generic in ID type (typically UUID but not constrained).
  - Uses dataclass with kw_only=True for explicit, readable instantiation.
  - Custom __eq__ and __hash__ based solely on entity_id.
  - created_at and updated_at are domain-level audit fields, not DB columns.
    Infrastructure (SQLAlchemy) maps them to real columns in module models.
  - eq=False on the dataclass so Python uses our custom implementations.

Usage:
    from dataclasses import dataclass, field
    from uuid import UUID, uuid4
    from app.shared.domain.entity import Entity

    @dataclass(kw_only=True, eq=False)
    class Trip(Entity[UUID]):
        entity_id: UUID = field(default_factory=uuid4)
        title: str = ""
        is_deleted: bool = False
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Generic, TypeVar

IDT = TypeVar("IDT")


@dataclass(kw_only=True, eq=False)
class Entity(Generic[IDT]):
    """
    Base class for all domain entities.

    Subclasses MUST provide the entity_id field. They should set eq=False
    so this base class's __eq__ is inherited.
    """

    entity_id: IDT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # ------------------------------------------------------------------ #
    # Identity-based equality                                              #
    # ------------------------------------------------------------------ #

    def __eq__(self, other: object) -> bool:
        """Two entities are equal iff they have the same type and ID."""
        if type(self) is not type(other):
            return NotImplemented
        return self.entity_id == other.entity_id  # type: ignore[union-attr]

    def __hash__(self) -> int:
        """Hash is based solely on entity_id so entities can be placed in sets/dicts."""
        return hash(self.entity_id)

    # ------------------------------------------------------------------ #
    # Lifecycle helpers                                                    #
    # ------------------------------------------------------------------ #

    def touch(self) -> None:
        """Update updated_at to the current UTC time. Call after mutating fields."""
        self.updated_at = datetime.now(UTC)

    # ------------------------------------------------------------------ #
    # Representation                                                       #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"{type(self).__name__}(entity_id={self.entity_id!r})"
