"""SQLAlchemyTripProposalRepository implementation."""

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.query import exclude_deleted
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
)
from app.modules.travel.planning.domain.value_objects.proposed_activity import (
    ProposedActivity,
)
from app.modules.travel.planning.domain.value_objects.proposed_day import ProposedDay
from app.modules.travel.planning.infrastructure.models.proposal_model import (
    TripProposalModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class SQLAlchemyTripProposalRepository:
    """SQLAlchemy implementation of ITripProposalRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, proposal_id: ProposalId) -> TripProposal | None:
        """Find a proposal by ID. Soft-deleted items are returned."""
        model = await self._session.get(TripProposalModel, proposal_id.value)
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        """Find the latest live proposal for a trip."""
        stmt = (
            select(TripProposalModel)
            .where(TripProposalModel.trip_id == trip_id.value)
        )
        stmt = exclude_deleted(stmt, TripProposalModel)
        stmt = (
            stmt.order_by(TripProposalModel.created_at.desc(), TripProposalModel.id.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_active_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        """Find any queued or generating proposal for the trip."""
        stmt = (
            select(TripProposalModel)
            .where(TripProposalModel.trip_id == trip_id.value)
            .where(
                TripProposalModel.status.in_(
                    [ProposalStatus.QUEUED.value, ProposalStatus.GENERATING.value]
                )
            )
        )
        stmt = exclude_deleted(stmt, TripProposalModel)
        stmt = (
            stmt.order_by(TripProposalModel.created_at.desc(), TripProposalModel.id.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: ProposalId | None = None,
    ) -> list[TripProposal]:
        """Find non-deleted proposals for an owner with keyset pagination."""
        stmt = (
            select(TripProposalModel)
            .where(TripProposalModel.owner_id == owner_id.value)
        )
        stmt = exclude_deleted(stmt, TripProposalModel)

        if after_id is not None:
            cursor_created_at = (
                select(TripProposalModel.created_at)
                .where(TripProposalModel.id == after_id.value)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    TripProposalModel.created_at < cursor_created_at,
                    and_(
                        TripProposalModel.created_at == cursor_created_at,
                        TripProposalModel.id < after_id.value,
                    ),
                )
            )

        stmt = (
            stmt.order_by(TripProposalModel.created_at.desc(), TripProposalModel.id.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars()]

    async def save(self, proposal: TripProposal) -> None:
        """Persist/update proposal aggregate."""
        existing = await self._session.get(TripProposalModel, proposal.proposal_id.value)
        if existing is None:
            self._session.add(self._to_new_model(proposal))
        else:
            self._apply_to_existing(proposal, existing)
        await self._session.flush()

    async def delete(self, proposal_id: ProposalId) -> None:
        """Hard-delete proposal row."""
        model = await self._session.get(TripProposalModel, proposal_id.value)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def exists(self, proposal_id: ProposalId) -> bool:
        """Check if proposal exists and is not soft-deleted."""
        stmt = (
            select(TripProposalModel.id)
            .where(TripProposalModel.id == proposal_id.value)
            .where(TripProposalModel.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ---------------------------------------------------------------------- #
    # Private mappers                                                          #
    # ---------------------------------------------------------------------- #

    def _to_domain(self, model: TripProposalModel) -> TripProposal:
        """Map ORM row to domain entity."""
        preferences = PlanningPreferences(
            destination=model.destination,
            duration_days=model.duration_days,
            budget_level=model.budget_level,
            interests=tuple(model.interests),
            travel_style=model.travel_style,
            special_requirements=model.special_requirements,
        )

        result: PlanningResult | None = None
        if model.result_summary is not None:
            days: list[ProposedDay] = []
            for d in model.result_days or []:
                activities: list[ProposedActivity] = []
                for a in d.get("activities", []):
                    activities.append(
                        ProposedActivity(
                            title=a["title"],
                            description=a["description"],
                            category=a["category"],
                            duration_minutes=a["duration_minutes"],
                            estimated_cost=a.get("estimated_cost"),
                        )
                    )
                days.append(
                    ProposedDay(
                        day_number=d["day_number"],
                        title=d["title"],
                        description=d["description"],
                        activities=tuple(activities),
                    )
                )
            result = PlanningResult(
                summary=model.result_summary,
                days=tuple(days),
                estimated_total_cost=model.estimated_total_cost,
                generated_at=model.generated_at,
            )

        return TripProposal(
            entity_id=ProposalId(value=model.id),
            trip_id=TripId(value=model.trip_id),
            owner_id=UserId(value=model.owner_id),
            preferences=preferences,
            status=ProposalStatus(model.status),
            result=result,
            failure_reason=model.failure_reason,
            expires_at=model.expires_at,
            version=model.version,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_new_model(self, proposal: TripProposal) -> TripProposalModel:
        """Map domain aggregate to a new ORM model."""
        res_summary, res_days, est_cost, gen_at = self._serialize_result(proposal.result)
        return TripProposalModel(
            id=proposal.proposal_id.value,
            owner_id=proposal.owner_id.value,
            trip_id=proposal.trip_id.value,
            status=proposal.status.value,
            destination=proposal.preferences.destination,
            duration_days=proposal.preferences.duration_days,
            budget_level=proposal.preferences.budget_level,
            interests=list(proposal.preferences.interests),
            travel_style=proposal.preferences.travel_style,
            special_requirements=proposal.preferences.special_requirements,
            result_summary=res_summary,
            result_days=res_days,
            estimated_total_cost=est_cost,
            generated_at=gen_at,
            failure_reason=proposal.failure_reason,
            expires_at=proposal.expires_at,
            version=1,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
            deleted_at=None,
        )

    def _apply_to_existing(self, proposal: TripProposal, model: TripProposalModel) -> None:
        """Apply mutable aggregate fields to an existing ORM model."""
        res_summary, res_days, est_cost, gen_at = self._serialize_result(proposal.result)
        model.status = proposal.status.value
        model.destination = proposal.preferences.destination
        model.duration_days = proposal.preferences.duration_days
        model.budget_level = proposal.preferences.budget_level
        model.interests = list(proposal.preferences.interests)
        model.travel_style = proposal.preferences.travel_style
        model.special_requirements = proposal.preferences.special_requirements
        model.result_summary = res_summary
        model.result_days = res_days
        model.estimated_total_cost = est_cost
        model.generated_at = gen_at
        model.failure_reason = proposal.failure_reason
        model.expires_at = proposal.expires_at
        model.deleted_at = proposal.deleted_at

    def _serialize_result(
        self, result: PlanningResult | None
    ) -> tuple[str | None, list[dict[str, Any]] | None, str | None, datetime | None]:
        """Serialize PlanningResult domain value object to DB fields."""
        if result is None:
            return None, None, None, None

        serialized_days: list[dict[str, Any]] = []
        for d in result.days:
            acts: list[dict[str, Any]] = []
            for a in d.activities:
                acts.append(
                    {
                        "title": a.title,
                        "description": a.description,
                        "category": a.category,
                        "duration_minutes": a.duration_minutes,
                        "estimated_cost": a.estimated_cost,
                    }
                )
            serialized_days.append(
                {
                    "day_number": d.day_number,
                    "title": d.title,
                    "description": d.description,
                    "activities": acts,
                }
            )

        return (
            result.summary,
            serialized_days,
            result.estimated_total_cost,
            result.generated_at,
        )
