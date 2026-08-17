"""Travel Planning CQRS command and query handlers."""

from __future__ import annotations

import logging

from app.modules.travel.planning.application.commands import (
    AcceptProposalCommand,
    RejectProposalCommand,
    RequestProposalCommand,
)
from app.modules.travel.planning.application.dtos import (
    AcceptProposalResult,
    GetProposalResult,
    ListProposalsResult,
    RejectProposalResult,
    RequestProposalResult,
)
from app.modules.travel.planning.application.planning_service import (
    PlanningService,
)
from app.modules.travel.planning.application.queries import (
    GetProposalByTripQuery,
    GetProposalQuery,
    ListProposalsQuery,
)

logger = logging.getLogger(__name__)


class RequestProposalHandler:
    """CQRS handler for RequestProposalCommand."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, command: RequestProposalCommand) -> RequestProposalResult:
        """Handle RequestProposalCommand."""
        logger.debug(
            "Handling RequestProposalCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.request_proposal(command)


class AcceptProposalHandler:
    """CQRS handler for AcceptProposalCommand."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, command: AcceptProposalCommand) -> AcceptProposalResult:
        """Handle AcceptProposalCommand."""
        logger.debug(
            "Handling AcceptProposalCommand",
            extra={"proposal_id": command.proposal_id, "requester_id": command.requester_id},
        )
        return await self._service.accept_proposal(command)


class RejectProposalHandler:
    """CQRS handler for RejectProposalCommand."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, command: RejectProposalCommand) -> RejectProposalResult:
        """Handle RejectProposalCommand."""
        logger.debug(
            "Handling RejectProposalCommand",
            extra={"proposal_id": command.proposal_id, "requester_id": command.requester_id},
        )
        return await self._service.reject_proposal(command)


class GetProposalHandler:
    """CQRS handler for GetProposalQuery."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, query: GetProposalQuery) -> GetProposalResult:
        """Handle GetProposalQuery."""
        logger.debug(
            "Handling GetProposalQuery",
            extra={"proposal_id": query.proposal_id, "requester_id": query.requester_id},
        )
        return await self._service.get_proposal(query)


class GetProposalByTripHandler:
    """CQRS handler for GetProposalByTripQuery."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, query: GetProposalByTripQuery) -> GetProposalResult:
        """Handle GetProposalByTripQuery."""
        logger.debug(
            "Handling GetProposalByTripQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_proposal_by_trip(query)


class ListProposalsHandler:
    """CQRS handler for ListProposalsQuery."""

    def __init__(self, service: PlanningService) -> None:
        self._service = service

    async def handle(self, query: ListProposalsQuery) -> ListProposalsResult:
        """Handle ListProposalsQuery."""
        logger.debug(
            "Handling ListProposalsQuery",
            extra={"owner_id": query.owner_id, "requester_id": query.requester_id},
        )
        return await self._service.list_proposals(query)
