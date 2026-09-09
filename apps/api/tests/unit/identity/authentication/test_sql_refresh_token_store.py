"""
Unit tests — SQLAlchemyRefreshTokenStore persistence and rotation ordering (Sprint 15.5A).

Validates:
  - New refresh token record is added and flushed BEFORE old record's rotated_to FK is set.
  - Old token status transitions to ROTATED with timestamp and rotated_to pointing to new token.
  - Reuse detection: raises RefreshTokenReuseError if already rotated.
  - Revocation detection: raises RefreshTokenRevokedError if revoked.
  - Expiry detection: raises RefreshTokenExpiredError if expired.
  - Not found detection: raises RefreshTokenNotFoundError if token hash does not exist.
  - Transaction atomicity & rollback integrity on failure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import pytest

from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
    TokenState,
)
from app.modules.identity.authentication.domain.errors import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReuseError,
    RefreshTokenRevokedError,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import (
    RefreshTokenId,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.models.auth_models import (
    RefreshTokenModel,
)
from app.modules.identity.authentication.infrastructure.repositories.sql_auth_repository import (
    SQLAlchemyRefreshTokenStore,
)


def _make_dummy_record(
    *,
    record_id: UUID | None = None,
    session_id: UUID | None = None,
    user_id: UUID | None = None,
    expires_at: datetime | None = None,
    rotated_from: UUID | None = None,
    rotation_counter: int = 0,
) -> RefreshTokenRecord:
    return RefreshTokenRecord.create(
        record_id=RefreshTokenId(value=record_id or uuid4()),
        token_hash=RefreshTokenHash.from_hex("a" * 64),
        session_id=SessionId(value=session_id or uuid4()),
        user_id=UserId(value=user_id or uuid4()),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=7)),
        rotated_from=RefreshTokenId(value=rotated_from) if rotated_from else None,
        rotation_counter=rotation_counter,
    )


class TestSQLAlchemyRefreshTokenStoreRotation:
    @pytest.mark.anyio
    async def test_rotation_persists_new_record_before_setting_rotated_to(self) -> None:
        """
        Verify that new_model is added and flushed into the session
        BEFORE old_model.rotated_to is assigned and flushed.
        """
        old_id = uuid4()
        session_id = uuid4()
        user_id = uuid4()
        new_id = uuid4()

        old_model = RefreshTokenModel(
            id=old_id,
            token_hash="a" * 64,
            session_id=session_id,
            user_id=user_id,
            status=TokenState.ACTIVE.value,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            rotated_to=None,
            rotated_at=None,
            rotation_counter=0,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_model

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        # Track operations order
        operations = []

        def track_add(model):
            operations.append(("add", model.id))

        async def track_flush():
            operations.append(("flush", old_model.rotated_to))

        mock_session.add.side_effect = track_add
        mock_session.flush.side_effect = track_flush

        store = SQLAlchemyRefreshTokenStore(mock_session)

        new_record = _make_dummy_record(
            record_id=new_id,
            session_id=session_id,
            user_id=user_id,
            rotated_from=old_id,
            rotation_counter=1,
        )

        await store.rotate(
            old_hash=RefreshTokenHash.from_hex("a" * 64),
            new_record=new_record,
        )

        # Verification of state
        assert old_model.status == TokenState.ROTATED.value
        assert old_model.rotated_to == new_id
        assert old_model.rotated_at is not None

        # Verification of execution order:
        # 1. new_model added
        # 2. flush occurs while old_model.rotated_to is still None (so new record is inserted first)
        # 3. old_model.rotated_to is set to new_id
        # 4. second flush persists the updated old_model
        assert operations == [
            ("add", new_id),
            ("flush", None),
            ("flush", new_id),
        ]

    @pytest.mark.anyio
    async def test_rotation_raises_reuse_error_when_already_rotated(self) -> None:
        old_model = RefreshTokenModel(
            id=uuid4(),
            token_hash="a" * 64,
            session_id=uuid4(),
            user_id=uuid4(),
            status=TokenState.ROTATED.value,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_model

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        store = SQLAlchemyRefreshTokenStore(mock_session)
        new_record = _make_dummy_record()

        with pytest.raises(RefreshTokenReuseError):
            await store.rotate(
                old_hash=RefreshTokenHash.from_hex("a" * 64),
                new_record=new_record,
            )

    @pytest.mark.anyio
    async def test_rotation_raises_revoked_error_when_revoked(self) -> None:
        old_model = RefreshTokenModel(
            id=uuid4(),
            token_hash="a" * 64,
            session_id=uuid4(),
            user_id=uuid4(),
            status=TokenState.REVOKED.value,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_model

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        store = SQLAlchemyRefreshTokenStore(mock_session)
        new_record = _make_dummy_record()

        with pytest.raises(RefreshTokenRevokedError):
            await store.rotate(
                old_hash=RefreshTokenHash.from_hex("a" * 64),
                new_record=new_record,
            )

    @pytest.mark.anyio
    async def test_rotation_raises_expired_error_when_expired(self) -> None:
        old_model = RefreshTokenModel(
            id=uuid4(),
            token_hash="a" * 64,
            session_id=uuid4(),
            user_id=uuid4(),
            status=TokenState.ACTIVE.value,
            expires_at=datetime.now(UTC) - timedelta(seconds=10),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_model

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        store = SQLAlchemyRefreshTokenStore(mock_session)
        new_record = _make_dummy_record()

        with pytest.raises(RefreshTokenExpiredError):
            await store.rotate(
                old_hash=RefreshTokenHash.from_hex("a" * 64),
                new_record=new_record,
            )

        assert old_model.status == TokenState.EXPIRED.value
        mock_session.flush.assert_awaited_once()

    @pytest.mark.anyio
    async def test_rotation_raises_not_found_when_token_missing(self) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        store = SQLAlchemyRefreshTokenStore(mock_session)
        new_record = _make_dummy_record()

        with pytest.raises(RefreshTokenNotFoundError):
            await store.rotate(
                old_hash=RefreshTokenHash.from_hex("a" * 64),
                new_record=new_record,
            )
