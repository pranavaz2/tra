"""
LoggingEventPublisher — dev/test implementation of EventPublisher.

Logs each domain event at DEBUG level. Suitable for local development
and CI where events should be observable but not yet wired to real consumers.

Production replacement:
  ARQEventPublisher (future task) will enqueue each event as an ARQ job:
    async def publish(self, events):
        for event in events:
            await self._arq.enqueue_job("dispatch_domain_event", event)

  Or a CompositeEventPublisher that fans out to multiple publishers:
    composite = CompositeEventPublisher([
        ARQEventPublisher(...),
        SentryAuditPublisher(...),
    ])
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.shared.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class LoggingEventPublisher:
    """
    Event publisher that writes events to the structured log at DEBUG level.

    Each published event is logged with its event_type, aggregate_id, and
    event_id. No consumer is invoked — this is purely observational.

    Suitable for: local dev, CI, integration tests where event content
    should be visible in the log but no real side-effects are needed.
    """

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            logger.debug(
                "Domain event published",
                extra={
                    "event_type": event.event_type,
                    "aggregate_id": event.aggregate_id,
                    "event_id": str(event.event_id),
                    "occurred_at": event.occurred_at.isoformat(),
                },
            )
