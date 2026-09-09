"""PlanningService — application-layer orchestrator for Travel Planning use cases."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.planning.application.commands import (
    AcceptProposalCommand,
    RejectProposalCommand,
    RequestProposalCommand,
)
from app.modules.travel.planning.application.dtos import (
    AcceptProposalResult,
    GetProposalResult,
    ListProposalsResult,
    ProposalListPage,
    ProposalSummary,
    RejectProposalResult,
    RequestProposalResult,
)
from app.modules.travel.planning.application.queries import (
    GetProposalByTripQuery,
    GetProposalQuery,
    ListProposalsQuery,
)
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.errors import (
    ProposalNotFoundError,
)
from app.modules.travel.planning.domain.repositories.interfaces import (
    ITripProposalRepository,
)
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.services.ai.base import PlanningEngine
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.infrastructure.clock import Clock

logger = logging.getLogger(__name__)


class PlanningService:
    """
    Application service for travel planning use cases.

    Orchestrates trip proposal requests, generation, acceptance/rejection.
    """

    def __init__(
        self,
        *,
        repository: ITripProposalRepository,
        trip_repository: ITripRepository,
        planning_engine: PlanningEngine,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
        itinerary_repository: IItineraryRepository | None = None,
    ) -> None:
        self._repository = repository
        self._trip_repository = trip_repository
        self._planning_engine = planning_engine
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider
        self._clock = clock
        self._itinerary_repository = itinerary_repository

    async def request_proposal(
        self, command: RequestProposalCommand
    ) -> RequestProposalResult:
        """
        Request a new travel planning proposal.

        Workflow:
          1. Validate trip exists and requester is the owner.
          2. Supersede any existing active proposal for this trip.
          3. Create a new proposal in QUEUED state.
          4. Transition to GENERATING state.
          5. Call the AI engine to generate the plan.
          6. Transition to READY on success or FAILED on error.
          7. Commit all state transitions and publish events.
        """
        logger.info("Requesting trip proposal", extra={"trip_id": command.trip_id})

        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            target_budget: Decimal | None = None
            if command.target_budget:
                target_budget = _parse_cost_to_decimal(command.target_budget)
            preferences = PlanningPreferences(
                destination=command.destination,
                duration_days=command.duration_days,
                budget_level=command.budget_level,
                interests=tuple(command.interests),
                travel_style=command.travel_style,
                special_requirements=command.special_requirements,
                currency=command.currency or "INR",
                target_budget=target_budget,
            )
        except TravixError as exc:
            return Failure(exc)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        # Load trip & authorize
        try:
            trip = await self._trip_repository.find_by_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load trip.", cause=exc))

        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))
        if trip.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this trip."))

        # Step 1: Cancel active, create new in QUEUED
        proposal_id = ProposalId(value=self._uuid_provider.generate())
        proposal = TripProposal.create(
            proposal_id=proposal_id,
            trip_id=trip_id,
            owner_id=requester_id,
            preferences=preferences,
        )

        try:
            async with self._uow:
                active_proposal = await self._repository.find_active_by_trip_id(trip_id)
                if active_proposal:
                    active_proposal.fail("superseded")
                    await self._repository.save(active_proposal)
                    # Publish the fail event for superseded proposal
                    await self._publish(active_proposal.pop_events(), context="supersede_proposal")

                await self._repository.save(proposal)
                await self._uow.commit()
        except Exception as exc:
            logger.error("Failed to persist queued proposal", extra={"reason": str(exc)})
            return Failure(InfrastructureError("Failed to save queued proposal.", cause=exc))

        await self._publish(proposal.pop_events(), context="queue_proposal")

        # Step 2: Transition to GENERATING
        try:
            async with self._uow:
                # Reload or modify in-memory
                proposal.start_generation()
                await self._repository.save(proposal)
                await self._uow.commit()
        except Exception as exc:
            logger.error("Failed to persist generating status", extra={"reason": str(exc)})
            return Failure(InfrastructureError("Failed to start proposal generation.", cause=exc))

        await self._publish(proposal.pop_events(), context="start_generation")

        # Step 3: Run AI generation
        try:
            result = await self._planning_engine.generate_plan(preferences)
            expires_at = self._clock.now() + timedelta(hours=24)
            async with self._uow:
                proposal.complete_generation(result, expires_at)
                await self._repository.save(proposal)
                await self._uow.commit()
        except Exception as exc:
            logger.exception("AI generation failed or persistence failed")
            # Mark proposal as FAILED
            try:
                async with self._uow:
                    proposal.fail(str(exc))
                    await self._repository.save(proposal)
                    await self._uow.commit()
            except Exception as inner_exc:
                logger.error("Failed to mark proposal as failed", extra={"reason": str(inner_exc)})

        await self._publish(proposal.pop_events(), context="complete_generation")
        return Success(ProposalSummary.from_aggregate(proposal))

    async def accept_proposal(self, command: AcceptProposalCommand) -> AcceptProposalResult:
        """Accept a generated proposal and optionally populate the itinerary atomically."""
        logger.info("Accepting proposal", extra={"proposal_id": command.proposal_id})

        try:
            proposal_id = ProposalId.from_str(command.proposal_id)
            requester_id = UserId.from_str(command.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        itinerary = None
        try:
            async with self._uow:
                proposal = await self._repository.find_by_id(proposal_id)
                if proposal is None or proposal.is_deleted:
                    return Failure(ProposalNotFoundError(str(proposal_id)))
                if proposal.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this proposal."))

                proposal.accept()
                await self._repository.save(proposal)

                # Atomically apply to itinerary if requested and repository is configured
                if command.apply_to_itinerary and self._itinerary_repository:
                    itinerary = await self._itinerary_repository.find_by_trip_id(proposal.trip_id)
                    if itinerary is None or itinerary.is_deleted:
                        itinerary_id = ItineraryId(value=self._uuid_provider.generate())
                        itinerary = Itinerary.create(itinerary_id=itinerary_id, trip_id=proposal.trip_id)

                    if proposal.result and proposal.result.days:
                        for proposed_day in proposal.result.days:
                            existing_day = next(
                                (d for d in itinerary.days if d.day_number == proposed_day.day_number),
                                None,
                            )
                            if existing_day is None:
                                day_id = ItineraryDayId(value=self._uuid_provider.generate())
                                target_day = itinerary.add_day(
                                    day_id=day_id,
                                    day_number=proposed_day.day_number,
                                    title=proposed_day.title or f"Day {proposed_day.day_number}",
                                )
                            else:
                                target_day = existing_day

                            for act in proposed_day.activities:
                                item_id = ItineraryItemId(value=self._uuid_provider.generate())
                                item_type = _map_category_to_item_type(act.category)
                                desc = act.description or ""
                                if act.formatted_address:
                                    desc += f"\n📍 {act.formatted_address}"
                                if act.rating:
                                    desc += f" (★ {act.rating:.1f})"
                                cost_val = _parse_cost_to_decimal(act.estimated_cost)
                                # Detect currency from the cost string; fall back to preferences currency
                                item_currency = (
                                    _detect_currency(act.estimated_cost, proposal.preferences.currency)
                                    if cost_val is not None
                                    else None
                                )
                                itinerary.add_item(
                                    item_id=item_id,
                                    day_id=target_day.entity_id,
                                    title=ItemTitle(act.place_name or act.title),
                                    item_type=item_type,
                                    description=desc.strip() or None,
                                    cost=cost_val,
                                    currency=item_currency,
                                )

                    await self._itinerary_repository.save(itinerary)

                await self._uow.commit()
        except TravixError as exc:
            logger.exception("TravixError in accept_proposal: %s", exc)
            return Failure(exc)
        except Exception as exc:
            logger.exception("Unexpected exception in accept_proposal: %s", exc)
            return Failure(InfrastructureError("Failed to accept proposal.", cause=exc))

        await self._publish(proposal.pop_events(), context="accept_proposal")
        if itinerary:
            await self._publish(itinerary.pop_events(), context="populate_itinerary")
        return Success(ProposalSummary.from_aggregate(proposal))

    async def reject_proposal(self, command: RejectProposalCommand) -> RejectProposalResult:
        """Reject a generated proposal."""
        logger.info("Rejecting proposal", extra={"proposal_id": command.proposal_id})

        try:
            proposal_id = ProposalId.from_str(command.proposal_id)
            requester_id = UserId.from_str(command.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                proposal = await self._repository.find_by_id(proposal_id)
                if proposal is None or proposal.is_deleted:
                    return Failure(ProposalNotFoundError(str(proposal_id)))
                if proposal.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this proposal."))

                proposal.reject()
                await self._repository.save(proposal)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to reject proposal.", cause=exc))

        await self._publish(proposal.pop_events(), context="reject_proposal")
        return Success(ProposalSummary.from_aggregate(proposal))

    async def get_proposal(self, query: GetProposalQuery) -> GetProposalResult:
        """Retrieve a proposal by ID."""
        try:
            proposal_id = ProposalId.from_str(query.proposal_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            proposal = await self._repository.find_by_id(proposal_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load proposal.", cause=exc))

        if proposal is None or proposal.is_deleted:
            return Failure(ProposalNotFoundError(str(proposal_id)))
        if proposal.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this proposal."))

        # Lazy check and update expiration if status is READY but TTL passed
        if proposal.status == ProposalStatus.READY and proposal.is_expired:
            try:
                async with self._uow:
                    proposal.expire()
                    await self._repository.save(proposal)
                    await self._uow.commit()
                await self._publish(proposal.pop_events(), context="lazy_expire")
            except Exception as exc:
                logger.error("Failed to lazily expire proposal", extra={"reason": str(exc)})

        return Success(ProposalSummary.from_aggregate(proposal))

    async def get_proposal_by_trip(self, query: GetProposalByTripQuery) -> GetProposalResult:
        """Retrieve the latest proposal for a given trip ID."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            proposal = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load proposal.", cause=exc))

        if proposal is None or proposal.is_deleted:
            return Failure(ProposalNotFoundError(f"for trip '{trip_id}'"))
        if proposal.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this trip's proposals."))

        # Lazy check and update expiration if status is READY but TTL passed
        if proposal.status == ProposalStatus.READY and proposal.is_expired:
            try:
                async with self._uow:
                    proposal.expire()
                    await self._repository.save(proposal)
                    await self._uow.commit()
                await self._publish(proposal.pop_events(), context="lazy_expire")
            except Exception as exc:
                logger.error("Failed to lazily expire proposal", extra={"reason": str(exc)})

        return Success(ProposalSummary.from_aggregate(proposal))

    async def list_proposals(self, query: ListProposalsQuery) -> ListProposalsResult:
        """List proposals owned by owner_id with cursor-based pagination."""
        try:
            owner_id = UserId.from_str(query.owner_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        if owner_id != requester_id:
            return Failure(ForbiddenError("You can only list your own proposals."))

        after_id: ProposalId | None = None
        if query.cursor is not None:
            try:
                after_id = ProposalId.from_str(decode_cursor(query.cursor))
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.",
                        field="cursor",
                        value=query.cursor,
                    )
                )

        fetch_limit = query.limit + 1

        try:
            proposals = await self._repository.find_by_owner(
                owner_id, limit=fetch_limit, after_id=after_id
            )
        except Exception as exc:
            return Failure(InfrastructureError("Failed to list proposals.", cause=exc))

        has_more = len(proposals) > query.limit
        if has_more:
            proposals = proposals[: query.limit]

        next_cursor: str | None = None
        if has_more and proposals:
            next_cursor = encode_cursor(str(proposals[-1].proposal_id))

        return Success(
            ProposalPageResponse = ProposalListPage(
                items=tuple(ProposalSummary.from_aggregate(p) for p in proposals),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    async def _publish(self, events: Sequence[DomainEvent], *, context: str) -> None:
        """Publish domain events safely after successful commit."""
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Event publication failed",
                extra={
                    "context": context,
                    "event_count": len(events),
                    "reason": str(exc),
                },
            )


def _map_category_to_item_type(category: str | None) -> ItineraryItemType:
    if not category:
        return ItineraryItemType.ACTIVITY
    cat = category.lower()
    if any(k in cat for k in ("din", "food", "restaur", "meal")):
        return ItineraryItemType.RESTAURANT
    if any(k in cat for k in ("trans", "flight", "train", "drive")):
        return ItineraryItemType.TRANSPORT
    if any(k in cat for k in ("lodg", "hotel", "stay", "hostel")):
        return ItineraryItemType.LODGING
    return ItineraryItemType.ACTIVITY


def _parse_cost_to_decimal(cost_str: str | None) -> Decimal | None:
    if not cost_str:
        return None
    cleaned = "".join(c for c in cost_str if c.isdigit() or c == ".")
    if not cleaned:
        return None
    try:
        val = Decimal(cleaned)
        return val if val >= Decimal("0") else None
    except Exception:
        return None


_CURRENCY_SYMBOLS: dict[str, str] = {
    "₹": "INR",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "฿": "THB",
}


def _detect_currency(cost_str: str | None, default: str = "INR") -> str:
    """Infer currency from the cost string symbol; fall back to *default*."""
    if not cost_str:
        return default
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in cost_str:
            return code
    # Detect 3-letter currency codes like "USD", "INR", "EUR"
    match = re.search(r"\b([A-Z]{3})\b", cost_str)
    if match:
        return match.group(1)
    return default

