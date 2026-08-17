"""Repositories package initialization."""

from app.modules.travel.planning.infrastructure.repositories.proposal_repository import (
    SQLAlchemyTripProposalRepository,
)

__all__ = ["SQLAlchemyTripProposalRepository"]
