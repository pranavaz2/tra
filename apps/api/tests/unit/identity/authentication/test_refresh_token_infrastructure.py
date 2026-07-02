"""
Unit tests — Refresh Token Infrastructure (TASK-2.6).

Coverage:
  - PlainRefreshToken: generation, entropy, repr redaction
  - RefreshTokenHash: SHA-256 correctness, validation, repr
  - Sha256RefreshTokenHasher: determinism, correct digest, from_client round-trip
  - SecureRefreshTokenGenerator: uniqueness, length, URL-safe alphabet
  - RefreshTokenRecord: state machine transitions, is_usable/is_terminal predicates
  - InMemoryRefreshTokenStore: CRUD, rotation atomicity, reuse detection, revocation sweeps
  - RefreshTokenApplicationService: happy-path rotation, all failure scenarios
  - AuthenticationSession.revoke_due_to_token_reuse: event emission

All tests are async (pytest-anyio / asyncio mode).
No real database, no Redis, no network I/O — pure in-memory.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.identity.authentication.application.refresh_token_service import (
    RefreshTokenApplicationService,
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
    SessionExpiredError,
    SessionRevokedError,
)
from app.modules.identity.authentication.domain.events.authentication_events import (
    RefreshTokenReuseDetected,
    SessionRevokedDueToTokenReuse,
)
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.refresh_token_generator import (
    SecureRefreshTokenGenerator,
)
from app.modules.identity.authentication.infrastructure.refresh_token_hasher import (
    Sha256RefreshTokenHasher,
)
from app.modules.identity.authentication.infrastructure.refresh_token_store import (
    InMemoryRefreshTokenStore,
    InMemorySessionRepository,
)
from app.shared.domain.result import Failure, Success

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_URL_SAFE_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _future(days: int = 7) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _past(seconds: int = 1) -> datetime:
    return datetime.now(UTC) - timedelta(seconds=seconds)


def _make_record(
    *,
    status: TokenState = TokenState.ACTIVE,
    expires_at: datetime | None = None,
    session_id: SessionId | None = None,
    user_id: UserId | None = None,
) -> RefreshTokenRecord:
    hasher = Sha256RefreshTokenHasher()
    plain = PlainRefreshToken.generate()
    token_hash = hasher.hash(plain)
    return RefreshTokenRecord.create(
        record_id=RefreshTokenId.generate(),
        token_hash=token_hash,
        session_id=session_id or SessionId.generate(),
        user_id=user_id or UserId.generate(),
        expires_at=expires_at or _future(),
    )


def _make_session(
    *,
    session_id: SessionId | None = None,
    user_id: UserId | None = None,
    refresh_token_id: RefreshTokenId | None = None,
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> AuthenticationSession:
    sid = session_id or SessionId.generate()
    uid = user_id or UserId.generate()
    now = datetime.now(UTC)
    session = AuthenticationSession(
        entity_id=sid,
        user_id=uid,
        refresh_token_id=refresh_token_id or RefreshTokenId.generate(),
        expires_at=expires_at or _future(),
        last_active_at=now,
    )
    if revoked:
        session.revoke()
        session.pop_events()
    return session


def _make_service(
    store: InMemoryRefreshTokenStore | None = None,
    session_repo: InMemorySessionRepository | None = None,
) -> RefreshTokenApplicationService:
    return RefreshTokenApplicationService(
        token_store=store or InMemoryRefreshTokenStore(),
        session_repository=session_repo or InMemorySessionRepository(),
        generator=SecureRefreshTokenGenerator(),
        hasher=Sha256RefreshTokenHasher(),
        token_lifetime_days=7,
    )


# ===========================================================================
# 1. PlainRefreshToken value object
# ===========================================================================


class TestPlainRefreshToken:
    def test_generate_produces_url_safe_string(self) -> None:
        token = PlainRefreshToken.generate()
        assert all(c in _URL_SAFE_CHARS for c in token.value)

    def test_generate_entropy_length(self) -> None:
        # 32 bytes URL-safe base64 → 43 chars (ceil(32 * 4/3) rounded up to 4-byte block)
        token = PlainRefreshToken.generate()
        assert len(token.value) >= 40  # 256 bits → at least 40 base64 chars

    def test_generate_produces_unique_tokens(self) -> None:
        tokens = {PlainRefreshToken.generate().value for _ in range(1000)}
        assert len(tokens) == 1000

    def test_repr_is_redacted(self) -> None:
        token = PlainRefreshToken.generate()
        assert "[REDACTED]" in repr(token)
        assert token.value not in repr(token)

    def test_str_is_redacted(self) -> None:
        token = PlainRefreshToken.generate()
        assert str(token) == "[REDACTED]"

    def test_fstring_is_redacted(self) -> None:
        token = PlainRefreshToken.generate()
        interpolated = f"token={token}"
        assert "[REDACTED]" in interpolated
        assert token.value not in interpolated

    def test_as_client_token_returns_raw_value(self) -> None:
        token = PlainRefreshToken.generate()
        assert token.as_client_token() == token.value

    def test_from_client_wraps_string(self) -> None:
        raw = "test-token-abc123"
        token = PlainRefreshToken.from_client(raw)
        assert token.as_client_token() == raw

    def test_from_client_repr_is_redacted(self) -> None:
        token = PlainRefreshToken.from_client("secret-value")
        assert "secret-value" not in repr(token)

    def test_frozen_cannot_mutate(self) -> None:
        token = PlainRefreshToken.generate()
        with pytest.raises((AttributeError, TypeError)):
            token.value = "overwritten"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        raw = PlainRefreshToken.generate().value
        a = PlainRefreshToken.from_client(raw)
        b = PlainRefreshToken.from_client(raw)
        assert a == b

    def test_inequality_different_values(self) -> None:
        assert PlainRefreshToken.generate() != PlainRefreshToken.generate()


# ===========================================================================
# 2. RefreshTokenHash value object
# ===========================================================================


class TestRefreshTokenHash:
    _VALID_HASH = "a" * 64  # 64 lowercase hex chars

    def test_valid_construction(self) -> None:
        h = RefreshTokenHash(value=self._VALID_HASH)
        assert h.value == self._VALID_HASH

    def test_rejects_wrong_length(self) -> None:
        from app.shared.domain.errors import ValidationError

        with pytest.raises(ValidationError):
            RefreshTokenHash(value="abc")

    def test_rejects_non_hex(self) -> None:
        from app.shared.domain.errors import ValidationError

        with pytest.raises(ValidationError):
            RefreshTokenHash(value="G" * 64)

    def test_rejects_uppercase(self) -> None:
        from app.shared.domain.errors import ValidationError

        with pytest.raises(ValidationError):
            RefreshTokenHash(value="A" * 64)

    def test_from_hex_normalises_lowercase(self) -> None:
        h = RefreshTokenHash.from_hex("A" * 64)
        assert h.value == "a" * 64

    def test_repr_shows_prefix_only(self) -> None:
        h = RefreshTokenHash(value="ab" * 32)
        r = repr(h)
        assert "sha256:" in r
        assert len(r) < 100  # not the full 64-char hash

    def test_frozen_immutable(self) -> None:
        h = RefreshTokenHash(value=self._VALID_HASH)
        with pytest.raises((AttributeError, TypeError)):
            h.value = "x" * 64  # type: ignore[misc]


# ===========================================================================
# 3. SHA-256 hasher
# ===========================================================================


class TestSha256RefreshTokenHasher:
    def setup_method(self) -> None:
        self.hasher = Sha256RefreshTokenHasher()

    def test_produces_64_char_hex(self) -> None:
        token = PlainRefreshToken.generate()
        h = self.hasher.hash(token)
        assert len(h.value) == 64
        assert all(c in "0123456789abcdef" for c in h.value)

    def test_deterministic(self) -> None:
        token = PlainRefreshToken.from_client("stable-value")
        assert self.hasher.hash(token) == self.hasher.hash(token)

    def test_matches_standard_sha256(self) -> None:
        raw = "test-token-abc"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        h = self.hasher.hash(PlainRefreshToken.from_client(raw))
        assert h.value == expected

    def test_different_tokens_produce_different_hashes(self) -> None:
        a = PlainRefreshToken.generate()
        b = PlainRefreshToken.generate()
        assert self.hasher.hash(a) != self.hasher.hash(b)

    def test_from_client_round_trip(self) -> None:
        """Hashing a from_client token produces the same result as hashing generate()."""
        gen = PlainRefreshToken.generate()
        client = PlainRefreshToken.from_client(gen.value)
        assert self.hasher.hash(gen) == self.hasher.hash(client)


# ===========================================================================
# 4. SecureRefreshTokenGenerator
# ===========================================================================


class TestSecureRefreshTokenGenerator:
    def setup_method(self) -> None:
        self.gen = SecureRefreshTokenGenerator()

    def test_returns_plain_refresh_token(self) -> None:
        token = self.gen.generate()
        assert isinstance(token, PlainRefreshToken)

    def test_unique_tokens(self) -> None:
        tokens = {self.gen.generate().value for _ in range(500)}
        assert len(tokens) == 500

    def test_url_safe(self) -> None:
        for _ in range(50):
            token = self.gen.generate()
            assert all(c in _URL_SAFE_CHARS for c in token.value)

    def test_repr_redacted(self) -> None:
        token = self.gen.generate()
        assert "[REDACTED]" in repr(token)


# ===========================================================================
# 5. RefreshTokenRecord state machine
# ===========================================================================


class TestRefreshTokenRecord:
    def test_create_sets_active_status(self) -> None:
        record = _make_record()
        assert record.status == TokenState.ACTIVE

    def test_is_usable_when_active_and_not_expired(self) -> None:
        record = _make_record()
        assert record.is_usable is True

    def test_is_not_usable_when_expired(self) -> None:
        record = _make_record(expires_at=_past())
        assert record.is_usable is False

    def test_is_not_usable_when_rotated(self) -> None:
        record = _make_record()
        record.mark_rotated()
        assert record.is_usable is False

    def test_is_not_usable_when_revoked(self) -> None:
        record = _make_record()
        record.revoke()
        assert record.is_usable is False

    def test_mark_rotated_transition(self) -> None:
        record = _make_record()
        record.mark_rotated()
        assert record.status == TokenState.ROTATED
        assert record.is_terminal is True

    def test_mark_rotated_idempotent_from_revoked(self) -> None:
        record = _make_record()
        record.revoke()
        record.mark_rotated()  # No-op — already terminal
        assert record.status == TokenState.REVOKED

    def test_mark_expired_transition(self) -> None:
        record = _make_record()
        record.mark_expired()
        assert record.status == TokenState.EXPIRED
        assert record.is_terminal is True

    def test_revoke_transition(self) -> None:
        record = _make_record()
        record.revoke()
        assert record.status == TokenState.REVOKED
        assert record.revoked_at is not None
        assert record.is_terminal is True

    def test_revoke_idempotent(self) -> None:
        record = _make_record()
        record.revoke()
        first_revoked_at = record.revoked_at
        record.revoke()  # Second call is a no-op
        assert record.revoked_at == first_revoked_at

    def test_rotated_can_be_revoked(self) -> None:
        record = _make_record()
        record.mark_rotated()
        record.revoke()
        assert record.status == TokenState.REVOKED

    def test_mark_used_records_timestamp(self) -> None:
        record = _make_record()
        assert record.last_used_at is None
        record.mark_used()
        assert record.last_used_at is not None

    def test_rotation_chain_fields(self) -> None:
        parent_id = RefreshTokenId.generate()
        record = RefreshTokenRecord.create(
            record_id=RefreshTokenId.generate(),
            token_hash=RefreshTokenHash.from_hex("a" * 64),
            session_id=SessionId.generate(),
            user_id=UserId.generate(),
            expires_at=_future(),
            rotated_from=parent_id,
            rotation_counter=3,
        )
        assert record.rotated_from == parent_id
        assert record.rotation_counter == 3

    def test_device_fields_stored(self) -> None:
        record = RefreshTokenRecord.create(
            record_id=RefreshTokenId.generate(),
            token_hash=RefreshTokenHash.from_hex("b" * 64),
            session_id=SessionId.generate(),
            user_id=UserId.generate(),
            expires_at=_future(),
            device_id="device-123",
            device_name="iPhone 15",
            platform="ios",
        )
        assert record.device_id == "device-123"
        assert record.device_name == "iPhone 15"
        assert record.platform == "ios"


# ===========================================================================
# 6. InMemoryRefreshTokenStore
# ===========================================================================


class TestInMemoryRefreshTokenStore:
    async def test_save_and_find_by_hash(self) -> None:
        store = InMemoryRefreshTokenStore()
        record = _make_record()
        await store.save(record)
        found = await store.find_by_hash(record.token_hash)
        assert found is record

    async def test_find_by_hash_returns_none_for_unknown(self) -> None:
        store = InMemoryRefreshTokenStore()
        unknown_hash = Sha256RefreshTokenHasher().hash(PlainRefreshToken.generate())
        assert await store.find_by_hash(unknown_hash) is None

    async def test_find_by_id_returns_record(self) -> None:
        store = InMemoryRefreshTokenStore()
        record = _make_record()
        await store.save(record)
        found = await store.find_by_id(record.entity_id)
        assert found is record

    async def test_find_active_by_session(self) -> None:
        store = InMemoryRefreshTokenStore()
        sid = SessionId.generate()
        record = _make_record(session_id=sid)
        await store.save(record)
        found = await store.find_active_by_session(sid)
        assert found is record

    async def test_find_active_by_session_returns_none_after_rotation(self) -> None:
        store = InMemoryRefreshTokenStore()
        sid = SessionId.generate()
        uid = UserId.generate()
        old_record = _make_record(session_id=sid, user_id=uid)
        await store.save(old_record)
        new_record = _make_record(session_id=sid, user_id=uid)
        await store.rotate(old_hash=old_record.token_hash, new_record=new_record)
        active = await store.find_active_by_session(sid)
        assert active is new_record

    async def test_successful_rotation(self) -> None:
        store = InMemoryRefreshTokenStore()
        old = _make_record()
        await store.save(old)
        new = _make_record(session_id=old.session_id, user_id=old.user_id)
        await store.rotate(old_hash=old.token_hash, new_record=new)
        assert old.status == TokenState.ROTATED
        assert new.status == TokenState.ACTIVE

    async def test_rotation_raises_reuse_error_on_already_rotated(self) -> None:
        store = InMemoryRefreshTokenStore()
        old = _make_record()
        await store.save(old)
        new1 = _make_record(session_id=old.session_id, user_id=old.user_id)
        new2 = _make_record(session_id=old.session_id, user_id=old.user_id)
        # First rotation succeeds
        await store.rotate(old_hash=old.token_hash, new_record=new1)
        # Second rotation with the same old hash fails
        with pytest.raises(RefreshTokenReuseError):
            await store.rotate(old_hash=old.token_hash, new_record=new2)

    async def test_rotation_raises_not_found_for_unknown_hash(self) -> None:
        store = InMemoryRefreshTokenStore()
        unknown = Sha256RefreshTokenHasher().hash(PlainRefreshToken.generate())
        new = _make_record()
        with pytest.raises(RefreshTokenNotFoundError):
            await store.rotate(old_hash=unknown, new_record=new)

    async def test_rotation_raises_revoked_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        old = _make_record()
        old.revoke()
        await store.save(old)
        new = _make_record(session_id=old.session_id, user_id=old.user_id)
        with pytest.raises(RefreshTokenRevokedError):
            await store.rotate(old_hash=old.token_hash, new_record=new)

    async def test_rotation_raises_expired_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        old = _make_record(expires_at=_past())
        await store.save(old)
        new = _make_record(session_id=old.session_id, user_id=old.user_id)
        with pytest.raises(RefreshTokenExpiredError):
            await store.rotate(old_hash=old.token_hash, new_record=new)

    async def test_revoke_all_for_session(self) -> None:
        store = InMemoryRefreshTokenStore()
        sid = SessionId.generate()
        uid = UserId.generate()
        records = [_make_record(session_id=sid, user_id=uid) for _ in range(3)]
        for r in records:
            await store.save(r)
        count = await store.revoke_all_for_session(sid)
        assert count == 3
        for r in records:
            assert r.status == TokenState.REVOKED

    async def test_revoke_all_for_user(self) -> None:
        store = InMemoryRefreshTokenStore()
        uid = UserId.generate()
        records = [_make_record(user_id=uid) for _ in range(4)]
        for r in records:
            await store.save(r)
        count = await store.revoke_all_for_user(uid)
        assert count == 4

    async def test_sha256_storage_verification(self) -> None:
        """Verify that no plaintext token value is stored in the store's internal state."""
        store = InMemoryRefreshTokenStore()
        token = PlainRefreshToken.generate()
        hasher = Sha256RefreshTokenHasher()
        token_hash = hasher.hash(token)
        record = RefreshTokenRecord.create(
            record_id=RefreshTokenId.generate(),
            token_hash=token_hash,
            session_id=SessionId.generate(),
            user_id=UserId.generate(),
            expires_at=_future(),
        )
        await store.save(record)

        # The store indexes by hash hex string — the plaintext never appears there.
        assert token.value not in store._by_hash
        assert token.value not in store._by_id
        # The token_hash IS the key
        assert token_hash.value in store._by_hash

    async def test_concurrent_rotation_atomicity(self) -> None:
        """
        Simulate concurrent rotation: only one of two tasks succeeds.

        Both tasks race to rotate the same old token. The asyncio.Lock
        in InMemoryRefreshTokenStore guarantees only one succeeds.
        """
        store = InMemoryRefreshTokenStore()
        old = _make_record()
        await store.save(old)

        new1 = _make_record(session_id=old.session_id, user_id=old.user_id)
        new2 = _make_record(session_id=old.session_id, user_id=old.user_id)

        successes = 0
        failures = 0

        async def try_rotate(new: RefreshTokenRecord) -> None:
            nonlocal successes, failures
            try:
                await store.rotate(old_hash=old.token_hash, new_record=new)
                successes += 1
            except (RefreshTokenReuseError, RefreshTokenNotFoundError):
                failures += 1

        await asyncio.gather(try_rotate(new1), try_rotate(new2))

        assert successes == 1
        assert failures == 1
        assert old.status == TokenState.ROTATED


# ===========================================================================
# 7. AuthenticationSession.revoke_due_to_token_reuse
# ===========================================================================


class TestAuthenticationSessionReuseRevocation:
    def test_revoke_due_to_token_reuse_emits_two_events(self) -> None:
        session = _make_session()
        session.revoke_due_to_token_reuse(reused_token_hash_prefix="abcd1234")
        events = session.pop_events()
        # Events: UserLoggedIn (from create), RefreshTokenReuseDetected, SessionRevokedDueToTokenReuse
        # But we used the non-factory constructor above, so only the two new events.
        reuse_events = [e for e in events if isinstance(e, RefreshTokenReuseDetected)]
        revoked_events = [e for e in events if isinstance(e, SessionRevokedDueToTokenReuse)]
        assert len(reuse_events) == 1
        assert len(revoked_events) == 1

    def test_reuse_event_carries_hash_prefix(self) -> None:
        session = _make_session()
        session.revoke_due_to_token_reuse(reused_token_hash_prefix="deadbeef")
        events = session.pop_events()
        reuse = next(e for e in events if isinstance(e, RefreshTokenReuseDetected))
        assert reuse.reused_token_hash_prefix == "deadbeef"
        assert reuse.session_id == str(session.session_id)
        assert reuse.user_id == str(session.user_id)

    def test_session_is_revoked_after_call(self) -> None:
        session = _make_session()
        assert session.is_active
        session.revoke_due_to_token_reuse()
        assert session.is_revoked

    def test_idempotent_on_already_revoked_session(self) -> None:
        session = _make_session(revoked=True)
        session.revoke_due_to_token_reuse()
        events = session.pop_events()
        # Should still emit SessionRevokedDueToTokenReuse but NOT a second RefreshTokenReuseDetected
        reuse_events = [e for e in events if isinstance(e, RefreshTokenReuseDetected)]
        assert len(reuse_events) == 0  # No new reuse event for already-revoked session


# ===========================================================================
# 8. RefreshTokenApplicationService — full lifecycle
# ===========================================================================


class TestRefreshTokenApplicationService:

    # ---- issue ----

    async def test_issue_returns_token_and_record_id(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)
        sid = SessionId.generate()
        uid = UserId.generate()

        result = await svc.issue(
            session_id=sid, user_id=uid, expires_at=_future()
        )

        assert isinstance(result, Success)
        plain, record_id = result.value
        assert isinstance(plain, PlainRefreshToken)
        assert isinstance(record_id, RefreshTokenId)

    async def test_issued_token_is_stored_as_hash(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)
        sid = SessionId.generate()
        uid = UserId.generate()

        result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = result.value  # type: ignore[misc]

        hasher = Sha256RefreshTokenHasher()
        expected_hash = hasher.hash(plain)
        stored = await store.find_by_hash(expected_hash)

        assert stored is not None
        assert str(stored.entity_id) == str(record_id)
        # Plaintext must NOT be stored
        assert plain.value not in str(store._by_hash.keys())

    async def test_issue_with_device_context(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)
        sid = SessionId.generate()
        uid = UserId.generate()

        result = await svc.issue(
            session_id=sid,
            user_id=uid,
            expires_at=_future(),
            device_id="d-001",
            device_name="Pixel 8",
            platform="android",
        )
        plain, record_id = result.value  # type: ignore[misc]

        hasher = Sha256RefreshTokenHasher()
        stored = await store.find_by_hash(hasher.hash(plain))
        assert stored is not None
        assert stored.device_id == "d-001"
        assert stored.device_name == "Pixel 8"
        assert stored.platform == "android"

    # ---- rotate (happy path) ----

    async def test_rotate_returns_new_token(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session = _make_session(
            session_id=sid, user_id=uid, refresh_token_id=record_id
        )
        session_repo.add_session(session)

        rotate_result = await svc.rotate(presented_token=plain.as_client_token())

        assert isinstance(rotate_result, Success)
        new_plain, new_record_id = rotate_result.value
        assert new_plain != plain
        assert new_record_id != record_id

    async def test_rotate_marks_old_token_as_rotated(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session_repo.add_session(_make_session(session_id=sid, user_id=uid, refresh_token_id=record_id))

        await svc.rotate(presented_token=plain.as_client_token())

        hasher = Sha256RefreshTokenHasher()
        old_record = await store.find_by_hash(hasher.hash(plain))
        assert old_record is not None
        assert old_record.status == TokenState.ROTATED

    async def test_rotate_increments_rotation_counter(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session_repo.add_session(_make_session(session_id=sid, user_id=uid, refresh_token_id=record_id))

        rotate_result = await svc.rotate(presented_token=plain.as_client_token())
        new_plain, new_record_id = rotate_result.value  # type: ignore[misc]

        hasher = Sha256RefreshTokenHasher()
        new_record = await store.find_by_hash(hasher.hash(new_plain))
        assert new_record is not None
        assert new_record.rotation_counter == 1

    # ---- rotate (failure paths) ----

    async def test_rotate_unknown_token_returns_not_found(self) -> None:
        svc = _make_service()
        result = await svc.rotate(presented_token="totally-unknown-token-xyz")
        assert isinstance(result, Failure)
        assert isinstance(result.error, RefreshTokenNotFoundError)

    async def test_rotate_expired_token_returns_expired_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        # Issue with past expiry
        issue_result = await svc.issue(
            session_id=sid, user_id=uid, expires_at=_past()
        )
        plain, record_id = issue_result.value  # type: ignore[misc]

        session_repo.add_session(_make_session(session_id=sid, user_id=uid, refresh_token_id=record_id))

        result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(result, Failure)
        assert isinstance(result.error, RefreshTokenExpiredError)

    async def test_rotate_revoked_token_returns_revoked_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        # Manually revoke the token
        hasher = Sha256RefreshTokenHasher()
        record = await store.find_by_hash(hasher.hash(plain))
        record.revoke()  # type: ignore[union-attr]
        await store.save(record)  # type: ignore[arg-type]

        session_repo.add_session(_make_session(session_id=sid, user_id=uid, refresh_token_id=record_id))

        result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(result, Failure)
        assert isinstance(result.error, RefreshTokenRevokedError)

    async def test_rotate_reused_rotated_token_triggers_session_revocation(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session = _make_session(session_id=sid, user_id=uid, refresh_token_id=record_id)
        session_repo.add_session(session)

        # First rotation — succeeds
        rotate1 = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(rotate1, Success)

        # Update session to reflect new token
        new_plain, new_record_id = rotate1.value
        stored_session = await session_repo.find_by_id(sid)
        assert stored_session is not None

        # Reuse the OLD token (which is now ROTATED) — stolen token scenario
        reuse_result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(reuse_result, Failure)
        assert isinstance(reuse_result.error, RefreshTokenReuseError)

        # The session must be revoked
        revoked_session = await session_repo.find_by_id(sid)
        assert revoked_session is not None
        assert revoked_session.is_revoked

    async def test_rotate_expired_session_returns_session_expired_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        # Session expired
        session_repo.add_session(
            _make_session(
                session_id=sid,
                user_id=uid,
                refresh_token_id=record_id,
                expires_at=_past(),
            )
        )

        result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(result, Failure)
        assert isinstance(result.error, SessionExpiredError)

    async def test_rotate_revoked_session_returns_session_revoked_error(self) -> None:
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session_repo.add_session(
            _make_session(session_id=sid, user_id=uid, refresh_token_id=record_id, revoked=True)
        )

        result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(result, Failure)
        assert isinstance(result.error, SessionRevokedError)

    # ---- revoke (single) ----

    async def test_revoke_single_token(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, _ = issue_result.value  # type: ignore[misc]

        result = await svc.revoke(presented_token=plain.as_client_token())
        assert isinstance(result, Success)

        hasher = Sha256RefreshTokenHasher()
        stored = await store.find_by_hash(hasher.hash(plain))
        assert stored is not None
        assert stored.status == TokenState.REVOKED

    async def test_revoke_unknown_token_returns_not_found(self) -> None:
        svc = _make_service()
        result = await svc.revoke(presented_token="unknown-token")
        assert isinstance(result, Failure)
        assert isinstance(result.error, RefreshTokenNotFoundError)

    # ---- revoke_all_for_session ----

    async def test_revoke_all_for_session(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)

        sid = SessionId.generate()
        uid = UserId.generate()
        for _ in range(3):
            await svc.issue(session_id=sid, user_id=uid, expires_at=_future())

        result = await svc.revoke_all_for_session(session_id=sid)
        assert isinstance(result, Success)
        assert result.value == 3

    # ---- revoke_all_for_user ----

    async def test_revoke_all_for_user(self) -> None:
        store = InMemoryRefreshTokenStore()
        svc = _make_service(store=store)

        uid = UserId.generate()
        for _ in range(5):
            await svc.issue(
                session_id=SessionId.generate(), user_id=uid, expires_at=_future()
            )

        result = await svc.revoke_all_for_user(user_id=uid)
        assert isinstance(result, Success)
        assert result.value == 5

    # ---- atomic rotation behaviour ----

    async def test_atomic_rotation_only_one_concurrent_succeeds(self) -> None:
        """
        Two concurrent rotate() calls for the same token:
        exactly one succeeds and one fails with RefreshTokenReuseError.
        """
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session = _make_session(session_id=sid, user_id=uid, refresh_token_id=record_id)
        session_repo.add_session(session)

        raw = plain.as_client_token()
        results = await asyncio.gather(
            svc.rotate(presented_token=raw),
            svc.rotate(presented_token=raw),
            return_exceptions=False,
        )

        successes = [r for r in results if isinstance(r, Success)]
        failures = [r for r in results if isinstance(r, Failure)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0].error, (RefreshTokenReuseError, RefreshTokenNotFoundError))

    # ---- session lifecycle transitions ----

    async def test_session_lifecycle_states_after_rotation(self) -> None:
        """After a successful rotation, the session's refresh_token_id is updated."""
        store = InMemoryRefreshTokenStore()
        session_repo = InMemorySessionRepository()
        svc = _make_service(store=store, session_repo=session_repo)

        sid = SessionId.generate()
        uid = UserId.generate()
        issue_result = await svc.issue(session_id=sid, user_id=uid, expires_at=_future())
        plain, record_id = issue_result.value  # type: ignore[misc]

        session = _make_session(session_id=sid, user_id=uid, refresh_token_id=record_id)
        session_repo.add_session(session)

        rotate_result = await svc.rotate(presented_token=plain.as_client_token())
        assert isinstance(rotate_result, Success)
        _, new_record_id = rotate_result.value

        updated_session = await session_repo.find_by_id(sid)
        assert updated_session is not None
        assert updated_session.refresh_token_id == new_record_id
