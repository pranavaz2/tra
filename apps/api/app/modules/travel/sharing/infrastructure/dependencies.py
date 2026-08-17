"""Sharing Infrastructure Layer — Dependency Injection Containers."""

from __future__ import annotations

import logging
from functools import lru_cache
from types import TracebackType
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DatabaseSession
from app.modules.identity.authentication.infrastructure.event_publisher import (
    LoggingEventPublisher,
)
from app.modules.travel.sharing.application.handlers import (
    AcceptInvitationHandler,
    ChangeMemberRoleHandler,
    CreateCollaborationHandler,
    DeclineInvitationHandler,
    DisablePublicSharingHandler,
    EnablePublicSharingHandler,
    GetCollaborationHandler,
    GetPublicTripHandler,
    InviteMemberHandler,
    ListInvitationsHandler,
    ListMembersHandler,
    RemoveMemberHandler,
    RevokeInvitationHandler,
    RotateShareTokenHandler,
)
from app.modules.travel.sharing.application.sharing_service import SharingService
from app.modules.travel.sharing.domain.repositories.interfaces import (
    IInvitationRepository,
    ITripCollaborationRepository,
)
from app.modules.travel.sharing.infrastructure.repositories.sharing_repository import (
    SQLAlchemyInvitationRepository,
    SQLAlchemyTripCollaborationRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import CurrentTripRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider
from app.shared.infrastructure.clock import Clock, SystemClock

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Session-bound Unit of Work                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class _SessionBoundUnitOfWork:
    """UnitOfWork that wraps an existing request-scoped AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _SessionBoundUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


# ──────────────────────────────────────────────────────────────────────────── #
# Infrastructure singletons                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_sharing_event_publisher() -> LoggingEventPublisher:
    return LoggingEventPublisher()


def get_sharing_event_publisher() -> EventPublisher:
    """Return the cached LoggingEventPublisher singleton."""
    return _build_sharing_event_publisher()


@lru_cache(maxsize=1)
def _build_sharing_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_sharing_uuid_provider() -> UUIDProvider:
    """Return the cached StandardUUIDProvider singleton."""
    return _build_sharing_uuid_provider()


@lru_cache(maxsize=1)
def _build_sharing_clock() -> SystemClock:
    return SystemClock()


def get_sharing_clock() -> Clock:
    """Return the cached SystemClock singleton."""
    return _build_sharing_clock()


CurrentSharingEventPublisher = Annotated[
    EventPublisher, Depends(get_sharing_event_publisher)
]
CurrentSharingUUIDProvider = Annotated[
    UUIDProvider, Depends(get_sharing_uuid_provider)
]
CurrentSharingClock = Annotated[Clock, Depends(get_sharing_clock)]


# ──────────────────────────────────────────────────────────────────────────── #
# Per-request dependencies (session-bound)                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_collaboration_repository(db: DatabaseSession) -> ITripCollaborationRepository:
    """Build a repository backed by the request-scoped session."""
    return SQLAlchemyTripCollaborationRepository(db)


def get_invitation_repository(db: DatabaseSession) -> IInvitationRepository:
    """Build an InvitationRepository backed by the request-scoped session."""
    return SQLAlchemyInvitationRepository(db)


def get_sharing_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    """Build a _SessionBoundUnitOfWork that shares the request session."""
    return _SessionBoundUnitOfWork(db)


CurrentCollaborationRepository = Annotated[
    ITripCollaborationRepository, Depends(get_collaboration_repository)
]
CurrentInvitationRepository = Annotated[
    IInvitationRepository, Depends(get_invitation_repository)
]
CurrentSharingUnitOfWork = Annotated[
    UnitOfWork, Depends(get_sharing_unit_of_work)
]


# ──────────────────────────────────────────────────────────────────────────── #
# SharingService                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


def get_sharing_service(
    repository: CurrentCollaborationRepository,
    invitation_repository: CurrentInvitationRepository,
    trip_repository: CurrentTripRepository,
    uow: CurrentSharingUnitOfWork,
    event_publisher: CurrentSharingEventPublisher,
    uuid_provider: CurrentSharingUUIDProvider,
    clock: CurrentSharingClock,
) -> SharingService:
    """Compose and return a fully-wired SharingService for this request."""
    return SharingService(
        repository=repository,
        invitation_repository=invitation_repository,
        trip_repository=trip_repository,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
        clock=clock,
    )


CurrentSharingService = Annotated[SharingService, Depends(get_sharing_service)]


# ──────────────────────────────────────────────────────────────────────────── #
# Command/Query Handlers                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def get_create_collaboration_handler(
    service: CurrentSharingService,
) -> CreateCollaborationHandler:
    return CreateCollaborationHandler(service)


def get_invite_member_handler(service: CurrentSharingService) -> InviteMemberHandler:
    return InviteMemberHandler(service)


def get_accept_invitation_handler(
    service: CurrentSharingService,
) -> AcceptInvitationHandler:
    return AcceptInvitationHandler(service)


def get_decline_invitation_handler(
    service: CurrentSharingService,
) -> DeclineInvitationHandler:
    return DeclineInvitationHandler(service)


def get_revoke_invitation_handler(
    service: CurrentSharingService,
) -> RevokeInvitationHandler:
    return RevokeInvitationHandler(service)


def get_change_member_role_handler(
    service: CurrentSharingService,
) -> ChangeMemberRoleHandler:
    return ChangeMemberRoleHandler(service)


def get_remove_member_handler(service: CurrentSharingService) -> RemoveMemberHandler:
    return RemoveMemberHandler(service)


def get_enable_public_sharing_handler(
    service: CurrentSharingService,
) -> EnablePublicSharingHandler:
    return EnablePublicSharingHandler(service)


def get_disable_public_sharing_handler(
    service: CurrentSharingService,
) -> DisablePublicSharingHandler:
    return DisablePublicSharingHandler(service)


def get_rotate_share_token_handler(
    service: CurrentSharingService,
) -> RotateShareTokenHandler:
    return RotateShareTokenHandler(service)


def get_get_collaboration_handler(
    service: CurrentSharingService,
) -> GetCollaborationHandler:
    return GetCollaborationHandler(service)


def get_list_members_handler(service: CurrentSharingService) -> ListMembersHandler:
    return ListMembersHandler(service)


def get_list_invitations_handler(
    service: CurrentSharingService,
) -> ListInvitationsHandler:
    return ListInvitationsHandler(service)


def get_public_trip_handler(service: CurrentSharingService) -> GetPublicTripHandler:
    return GetPublicTripHandler(service)


CurrentCreateCollaborationHandler = Annotated[
    CreateCollaborationHandler, Depends(get_create_collaboration_handler)
]
CurrentInviteMemberHandler = Annotated[
    InviteMemberHandler, Depends(get_invite_member_handler)
]
CurrentAcceptInvitationHandler = Annotated[
    AcceptInvitationHandler, Depends(get_accept_invitation_handler)
]
CurrentDeclineInvitationHandler = Annotated[
    DeclineInvitationHandler, Depends(get_decline_invitation_handler)
]
CurrentRevokeInvitationHandler = Annotated[
    RevokeInvitationHandler, Depends(get_revoke_invitation_handler)
]
CurrentChangeMemberRoleHandler = Annotated[
    ChangeMemberRoleHandler, Depends(get_change_member_role_handler)
]
CurrentRemoveMemberHandler = Annotated[
    RemoveMemberHandler, Depends(get_remove_member_handler)
]
CurrentEnablePublicSharingHandler = Annotated[
    EnablePublicSharingHandler, Depends(get_enable_public_sharing_handler)
]
CurrentDisablePublicSharingHandler = Annotated[
    DisablePublicSharingHandler, Depends(get_disable_public_sharing_handler)
]
CurrentRotateShareTokenHandler = Annotated[
    RotateShareTokenHandler, Depends(get_rotate_share_token_handler)
]
CurrentGetCollaborationHandler = Annotated[
    GetCollaborationHandler, Depends(get_get_collaboration_handler)
]
CurrentListMembersHandler = Annotated[
    ListMembersHandler, Depends(get_list_members_handler)
]
CurrentListInvitationsHandler = Annotated[
    ListInvitationsHandler, Depends(get_list_invitations_handler)
]
CurrentGetPublicTripHandler = Annotated[
    GetPublicTripHandler, Depends(get_public_trip_handler)
]
