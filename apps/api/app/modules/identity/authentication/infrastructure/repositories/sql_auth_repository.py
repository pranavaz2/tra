"""
SQLAlchemy implementations of identity repository interfaces.

Implements:
  - SQLAlchemyAuthRepository (AuthenticationRepository)
  - SQLAlchemySessionRepository (SessionRepository)
  - SQLAlchemyRefreshTokenStore (RefreshTokenRepository)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
    TokenState,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.errors import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReuseError,
    RefreshTokenRevokedError,
)
from app.modules.identity.authentication.domain.repositories.interfaces import (
    AuthenticationRepository,
    RefreshTokenRepository,
    SessionRepository,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.models.auth_models import (
    RefreshTokenModel,
    SessionModel,
    UserModel,
)

logger = logging.getLogger(__name__)


class SQLAlchemyAuthRepository:
    """Async SQLAlchemy implementation of AuthenticationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: UserModel) -> AuthenticationCredential:
        return AuthenticationCredential(
            entity_id=UserId(model.id),
            email=Email(model.email),
            password_hash=PasswordHash(model.password_hash),
            is_email_verified=model.is_email_verified,
            is_active=model.is_active,
            failed_login_count=model.failed_login_count,
            locked_until=model.locked_until,
            last_login_at=model.last_login_at,
            password_changed_at=model.password_changed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def find_by_email(self, email: Email) -> AuthenticationCredential | None:
        stmt = select(UserModel).where(
            UserModel.email == str(email),
            UserModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_user_id(self, user_id: UserId) -> AuthenticationCredential | None:
        raw_id = user_id.value if isinstance(user_id.value, UUID) else UUID(str(user_id))
        stmt = select(UserModel).where(
            UserModel.id == raw_id,
            UserModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def exists_with_email(self, email: Email) -> bool:
        stmt = select(func.count()).select_from(UserModel).where(
            UserModel.email == str(email),
            UserModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def save(self, credential: AuthenticationCredential) -> None:
        raw_id = credential.user_id.value if isinstance(credential.user_id.value, UUID) else UUID(str(credential.user_id))
        stmt = select(UserModel).where(UserModel.id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = UserModel(
                id=raw_id,
                email=str(credential.email),
                password_hash=credential.password_hash.value,
                is_email_verified=credential.is_email_verified,
                is_active=credential.is_active,
                failed_login_count=credential.failed_login_count,
                locked_until=credential.locked_until,
                last_login_at=credential.last_login_at,
                password_changed_at=credential.password_changed_at,
            )
            self._session.add(model)
        else:
            model.email = str(credential.email)
            model.password_hash = credential.password_hash.value
            model.is_email_verified = credential.is_email_verified
            model.is_active = credential.is_active
            model.failed_login_count = credential.failed_login_count
            model.locked_until = credential.locked_until
            model.last_login_at = credential.last_login_at
            model.password_changed_at = credential.password_changed_at

        await self._session.flush()


class SQLAlchemySessionRepository:
    """Async SQLAlchemy implementation of SessionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: SessionModel) -> AuthenticationSession:
        return AuthenticationSession(
            entity_id=SessionId(model.id),
            user_id=UserId(model.user_id),
            refresh_token_id=RefreshTokenId(model.refresh_token_id),
            expires_at=model.expires_at,
            last_active_at=model.last_active_at,
            revoked_at=model.revoked_at,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def find_by_id(self, session_id: SessionId) -> AuthenticationSession | None:
        raw_id = session_id.value if isinstance(session_id.value, UUID) else UUID(str(session_id))
        stmt = select(SessionModel).where(SessionModel.id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_user_id(self, user_id: UserId) -> list[AuthenticationSession]:
        raw_id = user_id.value if isinstance(user_id.value, UUID) else UUID(str(user_id))
        stmt = select(SessionModel).where(SessionModel.user_id == raw_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def find_by_refresh_token(
        self, refresh_token_id: RefreshTokenId
    ) -> AuthenticationSession | None:
        raw_id = refresh_token_id.value if isinstance(refresh_token_id.value, UUID) else UUID(str(refresh_token_id))
        stmt = select(SessionModel).where(SessionModel.refresh_token_id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def save(self, session: AuthenticationSession) -> None:
        raw_id = session.entity_id.value if isinstance(session.entity_id.value, UUID) else UUID(str(session.entity_id))
        raw_user_id = session.user_id.value if isinstance(session.user_id.value, UUID) else UUID(str(session.user_id))
        raw_token_id = (
            session.refresh_token_id.value
            if isinstance(session.refresh_token_id.value, UUID)
            else UUID(str(session.refresh_token_id))
        )

        stmt = select(SessionModel).where(SessionModel.id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = SessionModel(
                id=raw_id,
                user_id=raw_user_id,
                refresh_token_id=raw_token_id,
                expires_at=session.expires_at,
                last_active_at=session.last_active_at,
                revoked_at=session.revoked_at,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
            )
            self._session.add(model)
        else:
            model.refresh_token_id = raw_token_id
            model.expires_at = session.expires_at
            model.last_active_at = session.last_active_at
            model.revoked_at = session.revoked_at
            model.ip_address = session.ip_address
            model.user_agent = session.user_agent

        await self._session.flush()

    async def delete(self, session_id: SessionId) -> None:
        raw_id = session_id.value if isinstance(session_id.value, UUID) else UUID(str(session_id))
        stmt = delete(SessionModel).where(SessionModel.id == raw_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_all_for_user(self, user_id: UserId) -> None:
        raw_id = user_id.value if isinstance(user_id.value, UUID) else UUID(str(user_id))
        stmt = delete(SessionModel).where(SessionModel.user_id == raw_id)
        await self._session.execute(stmt)
        await self._session.flush()


class SQLAlchemyRefreshTokenStore:
    """Async SQLAlchemy implementation of RefreshTokenRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: RefreshTokenModel) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            entity_id=RefreshTokenId(model.id),
            token_hash=RefreshTokenHash(model.token_hash),
            session_id=SessionId(model.session_id),
            user_id=UserId(model.user_id),
            expires_at=model.expires_at,
            status=TokenState(model.status),
            revoked_at=model.revoked_at,
            rotated_from=RefreshTokenId(model.rotated_from) if model.rotated_from else None,
            rotation_counter=model.rotation_counter,
            device_id=model.device_id,
            device_name=model.device_name,
            platform=model.platform,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def find_by_hash(self, token_hash: RefreshTokenHash) -> RefreshTokenRecord | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == str(token_hash))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_id(self, record_id: RefreshTokenId) -> RefreshTokenRecord | None:
        raw_id = record_id.value if isinstance(record_id.value, UUID) else UUID(str(record_id))
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_active_by_session(
        self, session_id: SessionId
    ) -> RefreshTokenRecord | None:
        raw_id = session_id.value if isinstance(session_id.value, UUID) else UUID(str(session_id))
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.session_id == raw_id,
            RefreshTokenModel.status == "active",
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_all_by_session(
        self, session_id: SessionId
    ) -> list[RefreshTokenRecord]:
        raw_id = session_id.value if isinstance(session_id.value, UUID) else UUID(str(session_id))
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.session_id == raw_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, record: RefreshTokenRecord) -> None:
        raw_id = record.entity_id.value if isinstance(record.entity_id.value, UUID) else UUID(str(record.entity_id))
        raw_session_id = record.session_id.value if isinstance(record.session_id.value, UUID) else UUID(str(record.session_id))
        raw_user_id = record.user_id.value if isinstance(record.user_id.value, UUID) else UUID(str(record.user_id))
        raw_rotated_from = (
            record.rotated_from.value
            if record.rotated_from and isinstance(record.rotated_from.value, UUID)
            else UUID(str(record.rotated_from)) if record.rotated_from else None
        )

        stmt = select(RefreshTokenModel).where(RefreshTokenModel.id == raw_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = RefreshTokenModel(
                id=raw_id,
                token_hash=str(record.token_hash),
                session_id=raw_session_id,
                user_id=raw_user_id,
                status=record.status.value if hasattr(record.status, "value") else str(record.status),
                expires_at=record.expires_at,
                rotated_from=raw_rotated_from,
                revoked_at=record.revoked_at,
                device_id=record.device_id,
                device_name=record.device_name,
                platform=record.platform,
                rotation_counter=record.rotation_counter,
            )
            self._session.add(model)
        else:
            model.status = record.status.value if hasattr(record.status, "value") else str(record.status)
            model.expires_at = record.expires_at
            model.rotated_from = raw_rotated_from
            model.revoked_at = record.revoked_at
            model.device_id = record.device_id
            model.device_name = record.device_name
            model.platform = record.platform
            model.rotation_counter = record.rotation_counter

        await self._session.flush()

    async def rotate(
        self,
        *,
        old_hash: RefreshTokenHash,
        new_record: RefreshTokenRecord,
    ) -> None:
        # Atomic lock on the record to prevent race conditions
        stmt = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == str(old_hash))
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        old_model = result.scalar_one_or_none()

        if old_model is None:
            raise RefreshTokenNotFoundError()

        now = datetime.now(UTC)

        if old_model.status == TokenState.ROTATED.value:
            raise RefreshTokenReuseError()

        if old_model.status == TokenState.REVOKED.value:
            raise RefreshTokenRevokedError()

        if old_model.status == TokenState.EXPIRED.value or old_model.expires_at <= now:
            old_model.status = TokenState.EXPIRED.value
            await self._session.flush()
            raise RefreshTokenExpiredError()

        # 1. Insert new record first so its ID exists in the database
        new_id = new_record.entity_id.value if isinstance(new_record.entity_id.value, UUID) else UUID(str(new_record.entity_id))
        raw_session_id = new_record.session_id.value if isinstance(new_record.session_id.value, UUID) else UUID(str(new_record.session_id))
        raw_user_id = new_record.user_id.value if isinstance(new_record.user_id.value, UUID) else UUID(str(new_record.user_id))
        raw_rotated_from = (
            new_record.rotated_from.value
            if new_record.rotated_from and isinstance(new_record.rotated_from.value, UUID)
            else UUID(str(new_record.rotated_from)) if new_record.rotated_from else None
        )

        new_model = RefreshTokenModel(
            id=new_id,
            token_hash=str(new_record.token_hash),
            session_id=raw_session_id,
            user_id=raw_user_id,
            status=TokenState.ACTIVE.value,
            expires_at=new_record.expires_at,
            rotated_from=raw_rotated_from,
            device_id=new_record.device_id,
            device_name=new_record.device_name,
            platform=new_record.platform,
            rotation_counter=new_record.rotation_counter,
        )
        self._session.add(new_model)
        await self._session.flush()

        # 2. Mark old token as rotated and reference the newly inserted token
        old_model.status = TokenState.ROTATED.value
        old_model.rotated_at = now
        old_model.rotated_to = new_id
        await self._session.flush()

    async def revoke_all_for_session(self, session_id: SessionId) -> int:
        raw_id = session_id.value if isinstance(session_id.value, UUID) else UUID(str(session_id))
        now = datetime.now(UTC)
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.session_id == raw_id,
                RefreshTokenModel.status == "active",
            )
            .values(status="revoked", revoked_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    async def revoke_all_for_user(self, user_id: UserId) -> int:
        raw_id = user_id.value if isinstance(user_id.value, UUID) else UUID(str(user_id))
        now = datetime.now(UTC)
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == raw_id,
                RefreshTokenModel.status == "active",
            )
            .values(status="revoked", revoked_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
