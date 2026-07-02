"""
Travix AI — Domain Events

A Domain Event records that something of business significance HAPPENED.
Events are immutable facts — they describe the past, not intentions.

Design:
  - Frozen dataclass: immutable by construction.
  - event_id: UUID — unique identifier for deduplication.
  - occurred_at: UTC timestamp of when the event happened in the domain.
  - aggregate_id: str — the ID of the aggregate that raised the event,
    serialised as a string for cross-boundary compatibility.
  - event_type: property returning the class name (overrideable for versioning).

Usage — defining a concrete event:
    from dataclasses import dataclass, field
    from uuid import UUID
    from app.shared.domain.events import DomainEvent

    @dataclass(frozen=True)
    class TripCreated(DomainEvent):
        trip_id: UUID
        owner_id: UUID
        title: str

Usage — raising from an aggregate root:
    class Trip(AggregateRoot[UUID]):
        def create(self, title: str, owner_id: UUID) -> None:
            self.title = title
            self.push_event(TripCreated(
                aggregate_id=str(self.entity_id),
                trip_id=self.entity_id,
                owner_id=owner_id,
                title=title,
            ))

Event dispatch is handled by the application layer (use cases), not the
domain. The aggregate collects events; the use case pops and publishes them
after a successful save.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events.

    Subclasses add business-specific fields as frozen dataclass fields.
    All subclasses inherit the automatic event_id, occurred_at, and
    aggregate_id bookkeeping.
    """

    aggregate_id: str
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        """
        Machine-readable event type string.

        Defaults to the class name. Override in subclasses for explicit
        versioning or when the class name would expose internal structure.

        Example: TripCreated → "trip.created"
        """
        return type(self).__name__
