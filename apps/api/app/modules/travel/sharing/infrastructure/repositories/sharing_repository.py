"""SQLAlchemy repository implementations for the Sharing bounded context."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.query import exclude_deleted
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.entities.trip_member import TripMember
from app.modules.travel.sharing.domain.enums.invitation_status import InvitationStatus
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.sharing.domain.value_objects.invitation_id import InvitationId
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.sharing.domain.value_objects.share_token import ShareToken
from app.modules.travel.sharing.infrastructure.models.sharing_models import (
    InvitationModel,
    TripCollaborationModel,
    TripMemberModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class SQLAlchemyTripCollaborationRepository:
    """SQLAlchemy implementation of ITripCollaborationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(
        self, collaboration_id: CollaborationId
    ) -> TripCollaboration | None:
        """Find collaboration by primary ID."""
        stmt = select(TripCollaborationModel).where(
            TripCollaborationModel.id == collaboration_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_trip_id(self, trip_id: TripId) -> TripCollaboration | None:
        """Find the active (non-deleted) collaboration for a trip."""
        stmt = select(TripCollaborationModel).where(
            TripCollaborationModel.trip_id == trip_id.value
        )
        stmt = exclude_deleted(stmt, TripCollaborationModel)
        stmt = stmt.order_by(
            TripCollaborationModel.created_at.desc(),
            TripCollaborationModel.id.desc(),
        ).limit(1)

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_share_token(self, token: str) -> TripCollaboration | None:
        """Find an active, public collaboration by its share token."""
        stmt = (
            select(TripCollaborationModel)
            .where(TripCollaborationModel.share_token == token)
            .where(TripCollaborationModel.is_public.is_(True))
        )
        stmt = exclude_deleted(stmt, TripCollaborationModel)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def save(self, collaboration: TripCollaboration) -> None:
        """Persist or update a TripCollaboration aggregate."""
        stmt = select(TripCollaborationModel).where(
            TripCollaborationModel.id == collaboration.collaboration_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = self._to_new_model(collaboration)
            self._session.add(model)
        else:
            self._apply_to_existing(collaboration, model)

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Return True if a non-deleted collaboration exists for the trip."""
        stmt = select(TripCollaborationModel.id).where(
            TripCollaborationModel.trip_id == trip_id.value
        )
        stmt = exclude_deleted(stmt, TripCollaborationModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    # ------------------------------------------------------------------ #
    # Domain Mapping Helpers                                               #
    # ------------------------------------------------------------------ #

    def _to_domain(self, model: TripCollaborationModel) -> TripCollaboration:
        """Convert ORM model to domain aggregate."""
        members = [
            TripMember(
                entity_id=MemberId(m.id),
                user_id=UserId(m.user_id),
                role=MemberRole(m.role),
                joined_at=m.joined_at,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in model.members
        ]

        invitations = [
            Invitation(
                entity_id=InvitationId(i.id),
                invitee_email=i.invitee_email,
                role=MemberRole(i.role),
                status=InvitationStatus(i.status),
                token=i.token,
                expires_at=i.expires_at,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in model.invitations
        ]

        share_token: ShareToken | None = None
        if model.share_token is not None:
            share_token = ShareToken(value=model.share_token)

        collab = TripCollaboration(
            entity_id=CollaborationId(model.id),
            trip_id=TripId(model.trip_id),
            owner_id=UserId(model.owner_id),
            members=members,
            invitations=invitations,
            is_public=model.is_public,
            share_token=share_token,
            version=model.version,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

        # Clear pending events — we just loaded from persistence
        collab.pop_events()
        return collab

    def _to_new_model(self, collab: TripCollaboration) -> TripCollaborationModel:
        """Map brand-new domain aggregate to SQLAlchemy ORM model."""
        model = TripCollaborationModel(
            id=collab.collaboration_id.value,
            trip_id=collab.trip_id.value,
            owner_id=collab.owner_id.value,
            is_public=collab.is_public,
            share_token=str(collab.share_token) if collab.share_token else None,
            version=collab.version,
            deleted_at=collab.deleted_at,
            created_at=collab.created_at,
            updated_at=collab.updated_at,
        )

        model.members = [
            TripMemberModel(
                id=m.entity_id.value,
                collaboration_id=model.id,
                user_id=m.user_id.value,
                role=m.role.value,
                joined_at=m.joined_at,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in collab.members
        ]

        model.invitations = [
            InvitationModel(
                id=i.entity_id.value,
                collaboration_id=model.id,
                invitee_email=i.invitee_email,
                role=i.role.value,
                status=i.status.value,
                token=i.token,
                expires_at=i.expires_at,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in collab.invitations
        ]

        return model

    def _apply_to_existing(
        self, collab: TripCollaboration, model: TripCollaborationModel
    ) -> None:
        """Merge modifications from domain aggregate to existing ORM model."""
        model.is_public = collab.is_public
        model.share_token = str(collab.share_token) if collab.share_token else None
        model.deleted_at = collab.deleted_at
        model.updated_at = collab.updated_at
        model.version = collab.version

        # Sync members (insert, update, delete-orphan)
        existing_members = {m.id: m for m in model.members}
        new_members = []
        for domain_member in collab.members:
            mid = domain_member.entity_id.value
            if mid in existing_members:
                m_model = existing_members[mid]
                m_model.role = domain_member.role.value
                m_model.updated_at = domain_member.updated_at
            else:
                m_model = TripMemberModel(
                    id=mid,
                    collaboration_id=model.id,
                    user_id=domain_member.user_id.value,
                    role=domain_member.role.value,
                    joined_at=domain_member.joined_at,
                    created_at=domain_member.created_at,
                    updated_at=domain_member.updated_at,
                )
            new_members.append(m_model)
        model.members = new_members

        # Sync invitations (insert, update, delete-orphan)
        existing_invitations = {i.id: i for i in model.invitations}
        new_invitations = []
        for domain_inv in collab.invitations:
            iid = domain_inv.entity_id.value
            if iid in existing_invitations:
                i_model = existing_invitations[iid]
                i_model.status = domain_inv.status.value
                i_model.updated_at = domain_inv.updated_at
            else:
                i_model = InvitationModel(
                    id=iid,
                    collaboration_id=model.id,
                    invitee_email=domain_inv.invitee_email,
                    role=domain_inv.role.value,
                    status=domain_inv.status.value,
                    token=domain_inv.token,
                    expires_at=domain_inv.expires_at,
                    created_at=domain_inv.created_at,
                    updated_at=domain_inv.updated_at,
                )
            new_invitations.append(i_model)
        model.invitations = new_invitations


class SQLAlchemyInvitationRepository:
    """SQLAlchemy implementation of IInvitationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_token(self, token: str) -> Invitation | None:
        """Find a PENDING invitation by its opaque share token."""
        stmt = (
            select(InvitationModel)
            .where(InvitationModel.token == token)
            .where(InvitationModel.status == InvitationStatus.PENDING.value)
        )
        stmt = exclude_deleted(stmt, InvitationModel)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        return Invitation(
            entity_id=InvitationId(model.id),
            invitee_email=model.invitee_email,
            role=MemberRole(model.role),
            status=InvitationStatus(model.status),
            token=model.token,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
