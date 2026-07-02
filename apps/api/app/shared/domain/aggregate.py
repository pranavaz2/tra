"""
Travix AI — Aggregate Root

An Aggregate Root is the entry point into a consistency boundary.
Only the root can be directly referenced by external objects.
All mutations to entities within the aggregate go through the root.

Key responsibilities:
  1. Enforce invariants across the aggregate boundary.
  2. Collect domain events that occurred during a state change.
  3. Expose domain events to the application layer for dispatch.

Event lifecycle:
  - push_event()  — called inside the aggregate during state mutations.
  - pop_events()  — called by the use case AFTER a successful save(),
                    to dispatch events to subscribers.
  - Never dispatch events inside the aggregate or repository.

Usage:
    @dataclass(kw_only=True, eq=False)
    class Trip(AggregateRoot[UUID]):
        entity_id: UUID = field(default_factory=uuid4)
        title: str = ""

        def rename(self, new_title: str) -> None:
            if not new_title.strip():
                raise DomainError("Trip title cannot be blank.")
            self.title = new_title
            self.touch()
            self.push_event(TripRenamed(
                aggregate_id=str(self.entity_id),
                new_title=new_title,
            ))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from app.shared.domain.entity import Entity
from app.shared.domain.events import DomainEvent

IDT = TypeVar("IDT")


@dataclass(kw_only=True, eq=False)
class AggregateRoot(Entity[IDT], Generic[IDT]):
    """
    Base class for aggregate roots.

    Inherits identity semantics from Entity. Adds domain event collection.
    Subclasses define the aggregate boundary and enforce its invariants.
    """

    # Pending events: not included in equality, hash, or repr.
    # compare=False ensures __eq__ ignores this field (entity equality is ID-based).
    _pending_events: list[DomainEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )

    # ------------------------------------------------------------------ #
    # Event collection                                                     #
    # ------------------------------------------------------------------ #

    def push_event(self, event: DomainEvent) -> None:
        """
        Record a domain event.

        Called inside mutation methods (e.g. Trip.rename()). Never call
        this directly from outside the aggregate.
        """
        self._pending_events.append(event)

    def pop_events(self) -> list[DomainEvent]:
        """
        Return and clear all pending domain events.

        Called by the application layer (use case) after a successful
        repository.save(). The returned events are then dispatched to
        event handlers or published to a message broker.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    @property
    def has_pending_events(self) -> bool:
        """True if there are uncommitted domain events."""
        return bool(self._pending_events)
