"""
Event Publisher abstraction — shared kernel.

Application use cases collect domain events from aggregates and, after a
successful commit, publish them through this port. Consumers (notification
service, audit log, ARQ task queue) subscribe to specific event types.

Publishing happens AFTER commit — this guarantees that published events
correspond to persisted state changes. Publishing before commit risks
notifying consumers of changes that were later rolled back.

Usage:
    async with unit_of_work:
        aggregate.do_something()    # pushes domain event internally
        await repo.save(aggregate)
        await unit_of_work.commit()

    # Only after successful commit:
    events = aggregate.pop_events()
    await event_publisher.publish(events)

The interface is intentionally minimal. Implementations may:
  - Log events locally (LoggingEventPublisher — dev/test)
  - Enqueue events for async consumers (ARQEventPublisher — production)
  - Fan-out to multiple subscribers (CompositeEventPublisher)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.shared.domain.events import DomainEvent


@runtime_checkable
class EventPublisher(Protocol):
    """
    Port for publishing domain events after a successful transaction commit.

    Implementations must not raise exceptions on publish — a publish failure
    must not appear to roll back a committed transaction. Implementations
    should log publish errors and use best-effort delivery.
    """

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        """
        Publish a sequence of domain events.

        Called once after each successful commit, with all events from all
        aggregates modified in that transaction.

        The publisher is responsible for fan-out to all interested consumers.
        The application layer does not know about individual subscribers.

        Args:
            events: Ordered sequence of domain events (in the order they
                    were pushed to the aggregates). Empty sequences are a
                    no-op.
        """
        ...
