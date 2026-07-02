"""
Unit tests for LoginService — all 11 domain scenarios plus security invariants.

Test doubles are hand-crafted stubs (not mocks) to keep tests readable
and free of framework magic. Each test creates fresh repository instances
so there is no test-to-test state leakage.

Test doubles used:
  StubPasswordHasher      — verify always returns True, needs_rehash=False.
  WrongPasswordHasher     — verify always returns False.
  RehashingHasher         — verify returns True, needs_rehash=True (triggers rehash).
  FailingHasherOnVerify   — verify raises PasswordHashingError.
  StubJWTService          — returns predictable "test.access.token.<sub>" string.
  StubEventPublisher      — collects published events for assertion.
  StubRefreshTokenService — returns a fixed PlainRefreshToken + RefreshTokenId.
  FailingSessionRepo      — raises on save() to test persistence failure path.
  BlockingRiskService     — always returns RiskAction.BLOCK.

asyncio_mode = "auto" (pyproject.toml) — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.security.jwt.claims import AccessTokenClaims
from app.modules.identity.authentication.application.commands import LoginUserCommand
from app.modules.identity.authentication.application.interfaces import RiskAction, RiskDecision
from app.modules.identity.authentication.application.login_service import (
    LoginConfiguration,
    LoginService,
)
from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.errors import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    PasswordHashingError,
)
from app.modules.identity.authentication.domain.events.authentication_events import (
    LoginAttemptFailed,
    PasswordRehashed,
    UserLoggedIn,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.auth_repository import (
    InMemoryAuthRepository,
)
from app.modules.identity.authentication.infrastructure.policies import (
    DefaultAuthenticationPolicy,
    DefaultSessionPolicy,
)
from app.modules.identity.authentication.infrastructure.refresh_token_store import (
    InMemorySessionRepository,
)
from app.modules.identity.authentication.infrastructure.unit_of_work import InMemoryUnitOfWork
from app.shared.domain.clock import FrozenClock
from app.shared.domain.errors import InfrastructureError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.uuid_provider import FixedUUIDProvider

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_EMAIL = "alice@example.com"
_STRONG_PASSWORD = "CorrectHorseBatteryStaple!"
_FIXED_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

_USER_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
_SESSION_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")
_JTI_UUID = uuid.UUID("00000000-0000-4000-8000-000000000003")

_STUB_HASH = PasswordHash(value="$argon2id$stub$hash$for$testing$purposes")


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class StubPasswordHasher:
    """Always verifies successfully; never requires rehash."""

    def hash(self, plain_password: str) -> PasswordHash:
        return PasswordHash(value="$argon2id$stub$hash$for$testing$purposes")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        return True

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        return False


class WrongPasswordHasher:
    """Always returns False from verify (simulates wrong password)."""

    def hash(self, plain_password: str) -> PasswordHash:
        return PasswordHash(value="$argon2id$stub$hash$for$testing$purposes")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        return False

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        return False


class RehashingHasher:
    """
    verify() returns True, but needs_rehash() returns True on the first call.

    After the rehash, needs_rehash() returns False. Tracks calls to hash()
    so tests can assert the rehash occurred.
    """

    def __init__(self) -> None:
        self.hash_calls: int = 0
        self._needs_rehash = True

    def hash(self, plain_password: str) -> PasswordHash:
        self.hash_calls += 1
        self._needs_rehash = False
        return PasswordHash(value="$argon2id$rehashed$stub$hash$v2$value")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        return True

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        return self._needs_rehash


class FailingHasherOnVerify:
    """Raises PasswordHashingError on verify() — simulates hasher infrastructure failure."""

    def hash(self, plain_password: str) -> PasswordHash:
        return PasswordHash(value="$argon2id$stub$hash$for$testing$purposes")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        raise PasswordHashingError("Argon2 context initialisation failed.")

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        return False


class StubJWTService:
    """Returns a predictable access token string for any claims."""

    def create_access_token(self, claims: AccessTokenClaims) -> str:
        return f"test.access.token.{claims.sub}"

    def verify_access_token(self, token: str) -> Any:
        raise NotImplementedError

    def decode_access_token(self, token: str) -> Any:
        raise NotImplementedError

    def validate_claims(self, claims: AccessTokenClaims) -> None:
        pass


class StubEventPublisher:
    """Collects all published domain events for assertion."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)

    def event_types(self) -> list[str]:
        return [e.event_type for e in self.published]

    def events_of_type(self, event_class: type) -> list[Any]:
        return [e for e in self.published if isinstance(e, event_class)]


class StubRefreshTokenService:
    """Returns a fixed PlainRefreshToken and RefreshTokenId on issue()."""

    _PLAIN = PlainRefreshToken.generate()
    _ID = RefreshTokenId(uuid.UUID("ffffffff-0000-4000-8000-000000000001"))

    async def issue(
        self, *, session_id: Any, user_id: Any, expires_at: Any, **_: Any
    ) -> Any:
        return Success((self._PLAIN, self._ID))

    async def rotate(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_session(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_user(self, **_: Any) -> Any:
        raise NotImplementedError


class FailingRefreshTokenService:
    """Returns Failure from issue() — simulates token-service infrastructure failure."""

    async def issue(self, **_: Any) -> Any:
        return Failure(InfrastructureError("Redis unavailable."))

    async def rotate(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_session(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_user(self, **_: Any) -> Any:
        raise NotImplementedError


class FailingSessionRepo(InMemorySessionRepository):
    """Raises on save() — simulates DB write failure."""

    async def save(self, session: AuthenticationSession) -> None:
        raise Exception("DB connection reset by peer")


class BlockingRiskService:
    """Always returns RiskAction.BLOCK."""

    async def assess(self, **_: Any) -> RiskDecision:
        return RiskDecision(action=RiskAction.BLOCK, reason="test-block", risk_score=1.0)


class AllowingRiskService:
    """Always returns RiskAction.ALLOW."""

    async def assess(self, **_: Any) -> RiskDecision:
        return RiskDecision(action=RiskAction.ALLOW, risk_score=0.0)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_active_credential(
    *,
    is_email_verified: bool = True,
    is_active: bool = True,
    failed_login_count: int = 0,
    locked_until: datetime | None = None,
) -> AuthenticationCredential:
    """Create an active credential with a stub password hash for test use."""
    credential = AuthenticationCredential.create(
        user_id=UserId(_USER_UUID),
        email=Email(_VALID_EMAIL),
        password_hash=_STUB_HASH,
    )
    # Drain the UserRegistered event so it doesn't show in test assertions.
    credential.pop_events()
    if is_email_verified:
        credential.verify_email()
    if not is_active:
        credential.deactivate()
    if failed_login_count > 0:
        from datetime import timedelta as _td

        for _ in range(failed_login_count):
            credential.record_failed_login(
                max_attempts=999,  # don't trigger lockout in setup
                lockout_duration=_td(minutes=15),
            )
    if locked_until is not None:
        credential.locked_until = locked_until
    credential.pop_events()  # drain setup events
    return credential


def _make_service(
    *,
    auth_repo: InMemoryAuthRepository | None = None,
    require_email_verification: bool = False,
    hasher: Any = None,
    event_publisher: StubEventPublisher | None = None,
    refresh_token_service: Any = None,
    session_repo: Any = None,
    risk_service: Any = None,
    uuid_ids: list[uuid.UUID] | None = None,
) -> tuple[LoginService, InMemoryUnitOfWork, StubEventPublisher]:
    """
    Build a LoginService with controllable collaborators.

    Returns (service, uow, event_publisher) so tests can inspect state.
    """
    _auth_repo = auth_repo or InMemoryAuthRepository()
    _session_repo = session_repo or InMemorySessionRepository()
    _refresh_svc = refresh_token_service or StubRefreshTokenService()
    _jwt_svc = StubJWTService()
    _hasher = hasher or StubPasswordHasher()
    _session_policy = DefaultSessionPolicy(session_ttl_days=7)
    _auth_policy = DefaultAuthenticationPolicy(
        require_email_verification=require_email_verification,
        max_failed_attempts=5,
        lockout_duration_minutes=15,
    )
    _uow = InMemoryUnitOfWork()
    _pub = event_publisher or StubEventPublisher()
    _uuid = FixedUUIDProvider(uuid_ids or [_SESSION_UUID, _JTI_UUID])
    _clock = FrozenClock(_FIXED_NOW)
    _config = LoginConfiguration(
        access_token_lifetime_minutes=15,
        jwt_issuer="https://api.travix.ai",
        jwt_audience="travix-mobile",
    )

    service = LoginService(
        auth_repository=_auth_repo,
        session_repository=_session_repo,
        refresh_token_service=_refresh_svc,
        jwt_service=_jwt_svc,
        password_hasher=_hasher,
        session_policy=_session_policy,
        auth_policy=_auth_policy,
        unit_of_work=_uow,
        event_publisher=_pub,
        uuid_provider=_uuid,
        clock=_clock,
        config=_config,
        risk_service=risk_service,
    )
    return service, _uow, _pub


def _login_command(
    *,
    email: str = _VALID_EMAIL,
    password: str = _STRONG_PASSWORD,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "TestClient/1.0",
    device_id: str | None = None,
) -> LoginUserCommand:
    return LoginUserCommand(
        email=email,
        password=password,
        ip_address=ip_address,
        user_agent=user_agent,
        device_id=device_id,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Valid credentials — full happy path
# ---------------------------------------------------------------------------


class TestSuccessfulLogin:
    async def test_returns_success_with_session_summary(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        summary = result.value
        assert summary.user_id == UserId(_USER_UUID)
        assert summary.email == Email(_VALID_EMAIL)
        assert summary.session_id == SessionId(_SESSION_UUID)
        assert summary.is_email_verified is True

    async def test_access_token_uses_correct_sub(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        assert str(_USER_UUID) in result.value.access_token

    async def test_refresh_token_is_present(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        assert result.value.plain_refresh_token is not None

    async def test_expiry_timestamps_are_set(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        summary = result.value
        expected_access_exp = _FIXED_NOW + timedelta(minutes=15)
        expected_refresh_exp = _FIXED_NOW + timedelta(days=7)
        assert summary.access_token_expires_at == expected_access_exp
        assert summary.refresh_token_expires_at == expected_refresh_exp

    async def test_user_logged_in_event_published(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command())

        assert any(isinstance(e, UserLoggedIn) for e in pub.published)

    async def test_logged_in_event_carries_session_id(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command())

        logged_in = [e for e in pub.published if isinstance(e, UserLoggedIn)]
        assert len(logged_in) == 1
        assert logged_in[0].session_id == str(_SESSION_UUID)

    async def test_record_successful_login_resets_failed_count(self) -> None:
        repo = InMemoryAuthRepository()
        credential = _make_active_credential(failed_login_count=3)
        await repo.save(credential)
        service, _, _ = _make_service(auth_repo=repo)

        await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.failed_login_count == 0

    async def test_last_login_at_is_updated(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.last_login_at is not None


# ---------------------------------------------------------------------------
# Scenario 2: Email not found — generic failure (timing-equalized)
# ---------------------------------------------------------------------------


class TestEmailNotFound:
    async def test_returns_invalid_credentials_error(self) -> None:
        service, _, _ = _make_service()

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, InvalidCredentialsError)

    async def test_publishes_login_attempt_failed_event(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "invalid_credentials"
        assert failed_events[0].user_id is None  # unknown email — no user_id leaked

    async def test_timing_equalization_sets_dummy_hash(self) -> None:
        service, _, _ = _make_service()
        assert service._dummy_hash is None

        await service.execute(_login_command())

        # Dummy hash should be computed and cached after the first "email not found" attempt
        assert service._dummy_hash is not None

    async def test_subsequent_unknown_email_reuses_dummy_hash(self) -> None:
        service, _, _ = _make_service()

        await service.execute(_login_command())
        first_dummy = service._dummy_hash

        await service.execute(_login_command(email="other@example.com"))

        assert service._dummy_hash is first_dummy  # same object, not recomputed


# ---------------------------------------------------------------------------
# Scenario 3: Wrong password — failed attempt recorded
# ---------------------------------------------------------------------------


class TestWrongPassword:
    async def test_returns_invalid_credentials_error(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, hasher=WrongPasswordHasher())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, InvalidCredentialsError)

    async def test_failed_login_count_incremented(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, hasher=WrongPasswordHasher())

        await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.failed_login_count == 1

    async def test_multiple_failures_increment_count(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, hasher=WrongPasswordHasher())

        for _ in range(3):
            await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.failed_login_count == 3

    async def test_publishes_login_attempt_failed_event(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            auth_repo=repo, hasher=WrongPasswordHasher(), event_publisher=pub
        )

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "invalid_credentials"
        assert failed_events[0].user_id == str(_USER_UUID)

    async def test_error_message_does_not_distinguish_wrong_email_vs_wrong_password(
        self,
    ) -> None:
        """Both unknown email and wrong password must return the same error type and code."""
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())

        # Wrong password
        service_wrong, _, _ = _make_service(auth_repo=repo, hasher=WrongPasswordHasher())
        result_wrong = await service_wrong.execute(_login_command())

        # Unknown email (empty repo)
        service_unknown, _, _ = _make_service()
        result_unknown = await service_unknown.execute(_login_command())

        assert isinstance(result_wrong, Failure)
        assert isinstance(result_unknown, Failure)
        assert type(result_wrong.error) is type(result_unknown.error)
        assert result_wrong.error.code == result_unknown.error.code


# ---------------------------------------------------------------------------
# Scenario 4: Account disabled
# ---------------------------------------------------------------------------


class TestAccountDisabled:
    async def test_returns_account_disabled_error(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_active=False))
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AccountDisabledError)

    async def test_disabled_account_does_not_verify_password(self) -> None:
        """Password must not be verified for a disabled account (no CPU waste, no timing info)."""
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_active=False))
        # If verify() were called, FailingHasherOnVerify would raise PasswordHashingError.
        # We expect AccountDisabledError instead.
        service, _, _ = _make_service(auth_repo=repo, hasher=FailingHasherOnVerify())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AccountDisabledError)

    async def test_publishes_login_attempt_failed_event(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_active=False))
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "account_disabled"


# ---------------------------------------------------------------------------
# Scenario 5: Account locked
# ---------------------------------------------------------------------------


class TestAccountLocked:
    async def test_returns_account_locked_error(self) -> None:
        repo = InMemoryAuthRepository()
        locked_until = _FIXED_NOW + timedelta(minutes=10)
        await repo.save(_make_active_credential(locked_until=locked_until))
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AccountLockedError)

    async def test_locked_error_carries_locked_until(self) -> None:
        repo = InMemoryAuthRepository()
        locked_until = _FIXED_NOW + timedelta(minutes=10)
        await repo.save(_make_active_credential(locked_until=locked_until))
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, AccountLockedError)
        assert error.locked_until == locked_until

    async def test_locked_account_does_not_verify_password(self) -> None:
        repo = InMemoryAuthRepository()
        locked_until = _FIXED_NOW + timedelta(minutes=10)
        await repo.save(_make_active_credential(locked_until=locked_until))
        service, _, _ = _make_service(auth_repo=repo, hasher=FailingHasherOnVerify())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AccountLockedError)

    async def test_publishes_login_attempt_failed_event(self) -> None:
        repo = InMemoryAuthRepository()
        locked_until = _FIXED_NOW + timedelta(minutes=10)
        await repo.save(_make_active_credential(locked_until=locked_until))
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "account_locked"

    async def test_expired_lockout_allows_login(self) -> None:
        """A lock that has elapsed (locked_until in the past) must NOT block login."""
        repo = InMemoryAuthRepository()
        past_locked_until = _FIXED_NOW - timedelta(seconds=1)
        await repo.save(_make_active_credential(locked_until=past_locked_until))
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)


# ---------------------------------------------------------------------------
# Scenario 6: Email not verified
# ---------------------------------------------------------------------------


class TestEmailNotVerified:
    async def test_returns_email_not_verified_error_when_policy_requires(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_email_verified=False))
        service, _, _ = _make_service(auth_repo=repo, require_email_verification=True)

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, EmailNotVerifiedError)

    async def test_unverified_email_allowed_when_policy_does_not_require(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_email_verified=False))
        service, _, _ = _make_service(auth_repo=repo, require_email_verification=False)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)

    async def test_unverified_does_not_verify_password(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_email_verified=False))
        service, _, _ = _make_service(
            auth_repo=repo,
            require_email_verification=True,
            hasher=FailingHasherOnVerify(),
        )

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, EmailNotVerifiedError)

    async def test_publishes_login_attempt_failed_event(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential(is_email_verified=False))
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            auth_repo=repo, require_email_verification=True, event_publisher=pub
        )

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "email_not_verified"


# ---------------------------------------------------------------------------
# Scenario 7: Transparent password rehash
# ---------------------------------------------------------------------------


class TestTransparentPasswordRehash:
    async def test_rehash_occurs_transparently_on_login(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        hasher = RehashingHasher()
        service, _, _ = _make_service(auth_repo=repo, hasher=hasher)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        assert hasher.hash_calls == 1  # rehash was called

    async def test_rehash_updates_stored_hash(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, hasher=RehashingHasher())

        await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.password_hash.value != _STUB_HASH.value

    async def test_rehash_emits_password_rehashed_event(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, hasher=RehashingHasher(), event_publisher=pub)

        await service.execute(_login_command())

        rehash_events = [e for e in pub.published if isinstance(e, PasswordRehashed)]
        assert len(rehash_events) == 1
        assert rehash_events[0].user_id == str(_USER_UUID)

    async def test_rehash_does_not_emit_password_changed_event(self) -> None:
        """Transparent rehash must NOT trigger PasswordChanged (no user-visible change)."""
        from app.modules.identity.authentication.domain.events.authentication_events import (
            PasswordChanged,
        )

        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, hasher=RehashingHasher(), event_publisher=pub)

        await service.execute(_login_command())

        changed_events = [e for e in pub.published if isinstance(e, PasswordChanged)]
        assert len(changed_events) == 0

    async def test_rehash_does_not_update_password_changed_at(self) -> None:
        """Rehash must NOT reset password_changed_at — that timestamp tracks user intent."""
        repo = InMemoryAuthRepository()
        credential = _make_active_credential()
        original_changed_at = credential.password_changed_at
        await repo.save(credential)
        service, _, _ = _make_service(auth_repo=repo, hasher=RehashingHasher())

        await service.execute(_login_command())

        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.password_changed_at == original_changed_at

    async def test_no_rehash_when_not_needed(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command())

        rehash_events = [e for e in pub.published if isinstance(e, PasswordRehashed)]
        assert len(rehash_events) == 0


# ---------------------------------------------------------------------------
# Scenario 8: Risk assessment blocks login
# ---------------------------------------------------------------------------


class TestRiskAssessment:
    async def test_blocked_by_risk_service_returns_authentication_failed(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, risk_service=BlockingRiskService())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AuthenticationFailedError)

    async def test_risk_block_publishes_login_attempt_failed(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            auth_repo=repo, risk_service=BlockingRiskService(), event_publisher=pub
        )

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].failure_reason == "risk_blocked"

    async def test_risk_block_does_not_verify_password(self) -> None:
        """Password must not be verified after a risk BLOCK decision."""
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        # If verify() were called, FailingHasherOnVerify would raise PasswordHashingError.
        service, _, _ = _make_service(
            auth_repo=repo,
            risk_service=BlockingRiskService(),
            hasher=FailingHasherOnVerify(),
        )

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, AuthenticationFailedError)

    async def test_allow_risk_decision_proceeds_normally(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, risk_service=AllowingRiskService())

        result = await service.execute(_login_command())

        assert isinstance(result, Success)

    async def test_no_risk_service_defaults_to_allow(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, risk_service=None)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)

    async def test_risk_service_failure_is_fail_open(self) -> None:
        """If risk assessment raises, login must proceed (fail open, not fail closed)."""

        class RaisingRiskService:
            async def assess(self, **_: Any) -> RiskDecision:
                raise RuntimeError("Risk service timeout")

        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, risk_service=RaisingRiskService())

        result = await service.execute(_login_command())

        assert isinstance(result, Success)


# ---------------------------------------------------------------------------
# Scenario 9: Refresh token issuance
# ---------------------------------------------------------------------------


class TestRefreshTokenIssuance:
    async def test_refresh_token_in_summary_is_from_service(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo)

        result = await service.execute(_login_command())

        assert isinstance(result, Success)
        expected = StubRefreshTokenService._PLAIN
        assert result.value.plain_refresh_token is expected

    async def test_refresh_token_service_failure_returns_infrastructure_error(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(
            auth_repo=repo, refresh_token_service=FailingRefreshTokenService()
        )

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, InfrastructureError)


# ---------------------------------------------------------------------------
# Scenario 10: Session creation
# ---------------------------------------------------------------------------


class TestSessionCreation:
    async def test_session_carries_ip_address(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command(ip_address="192.168.1.1"))

        logged_in = [e for e in pub.published if isinstance(e, UserLoggedIn)]
        assert len(logged_in) == 1
        assert logged_in[0].ip_address == "192.168.1.1"

    async def test_session_carries_user_agent(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=repo, event_publisher=pub)

        await service.execute(_login_command(user_agent="Mozilla/5.0"))

        logged_in = [e for e in pub.published if isinstance(e, UserLoggedIn)]
        assert logged_in[0].user_agent == "Mozilla/5.0"

    async def test_session_repo_failure_returns_infrastructure_error(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(
            auth_repo=repo, session_repo=FailingSessionRepo()
        )

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, InfrastructureError)


# ---------------------------------------------------------------------------
# Scenario 11: Persistence failure — rollback
# ---------------------------------------------------------------------------


class _FailingSaveAuthRepo(InMemoryAuthRepository):
    """Pre-seeded repo that always raises on save() — simulates DB failure."""

    def __init__(self) -> None:
        super().__init__()
        cred = _make_active_credential()
        self._by_email[str(cred.email)] = cred
        self._by_user_id[str(cred.user_id)] = cred

    async def save(self, credential: AuthenticationCredential) -> None:
        raise Exception("DB write failed")


class TestPersistenceFailure:
    async def test_auth_repo_failure_on_successful_login_returns_infrastructure_error(
        self,
    ) -> None:
        service, _, _ = _make_service(auth_repo=_FailingSaveAuthRepo())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, InfrastructureError)

    async def test_uow_is_rolled_back_on_persistence_failure(self) -> None:
        service, uow, _ = _make_service(auth_repo=_FailingSaveAuthRepo())

        await service.execute(_login_command())

        assert uow.rolled_back is True
        assert uow.committed is False


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------


class TestSecurityInvariants:
    def test_login_command_repr_does_not_contain_password(self) -> None:
        cmd = LoginUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        assert _STRONG_PASSWORD not in repr(cmd)
        assert "[REDACTED]" in repr(cmd)

    def test_login_command_str_does_not_contain_password(self) -> None:
        cmd = LoginUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        assert _STRONG_PASSWORD not in str(cmd)

    def test_authenticated_session_summary_repr_does_not_contain_access_token(
        self,
    ) -> None:
        from app.modules.identity.authentication.application.dtos import (
            AuthenticatedSessionSummary,
        )

        summary = AuthenticatedSessionSummary(
            user_id=UserId(_USER_UUID),
            email=Email(_VALID_EMAIL),
            session_id=SessionId(_SESSION_UUID),
            access_token="eyJsensitivetoken",
            plain_refresh_token=PlainRefreshToken.generate(),
            access_token_expires_at=_FIXED_NOW + timedelta(minutes=15),
            refresh_token_expires_at=_FIXED_NOW + timedelta(days=7),
            is_email_verified=True,
        )
        assert "eyJsensitivetoken" not in repr(summary)
        assert "[REDACTED]" in repr(summary)

    def test_plain_refresh_token_repr_is_redacted(self) -> None:
        token = PlainRefreshToken.generate()
        raw = token.as_client_token()
        assert raw not in repr(token)
        assert "[REDACTED]" in repr(token)

    async def test_unknown_email_does_not_reveal_user_id_in_event(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)

        await service.execute(_login_command())

        failed_events = [e for e in pub.published if isinstance(e, LoginAttemptFailed)]
        assert all(e.user_id is None for e in failed_events)

    async def test_invalid_email_format_returns_validation_error(self) -> None:
        service, _, _ = _make_service()

        result = await service.execute(_login_command(email="not-an-email"))

        assert isinstance(result, Failure)
        # Should return an error from Email VO parsing, not InvalidCredentialsError
        assert not isinstance(result.error, InvalidCredentialsError)

    async def test_hasher_verify_infrastructure_failure_returns_hashing_error(self) -> None:
        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(auth_repo=repo, hasher=FailingHasherOnVerify())

        result = await service.execute(_login_command())

        assert isinstance(result, Failure)
        assert isinstance(result.error, PasswordHashingError)

    async def test_event_publisher_failure_does_not_roll_back_login(self) -> None:
        """A publish failure after commit must not appear to reverse the login."""

        class RaisingEventPublisher:
            async def publish(self, events: Sequence[DomainEvent]) -> None:
                raise RuntimeError("Message bus unavailable")

        repo = InMemoryAuthRepository()
        await repo.save(_make_active_credential())
        service, _, _ = _make_service(
            auth_repo=repo, event_publisher=RaisingEventPublisher()
        )

        result = await service.execute(_login_command())

        # Login still succeeds even if publishing fails
        assert isinstance(result, Success)
