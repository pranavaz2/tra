"""
Unit tests for RegistrationService — all 9 domain scenarios.

Test doubles are hand-crafted stubs (not mocks) to keep tests readable
and free of framework magic. Each test creates fresh repository instances
so there is no test-to-test state leakage.

Test doubles used:
  StubPasswordHasher    — synchronous, returns a predictable PasswordHash.
  FailingHasher         — raises PasswordHashingError to test scenario 6.
  StubJWTService        — returns a fixed "test.access.token" string.
  StubEventPublisher    — collects published events for assertion.
  FailingAuthRepo       — raises on save() to test scenario 7.

asyncio_mode = "auto" (pyproject.toml) — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.security.jwt.claims import AccessTokenClaims
from app.modules.identity.authentication.application.commands import RegisterUserCommand
from app.modules.identity.authentication.application.registration_service import (
    RegistrationConfiguration,
    RegistrationService,
)
from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.errors import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    PasswordHashingError,
    WeakPasswordError,
)
from app.modules.identity.authentication.domain.events.authentication_events import (
    EmailVerificationRequested,
    UserEmailAutoVerified,
    UserLoggedIn,
    UserRegistered,
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
    DefaultPasswordStrengthPolicy,
    DefaultSessionPolicy,
)
from app.modules.identity.authentication.infrastructure.refresh_token_store import (
    InMemoryRefreshTokenStore,
    InMemorySessionRepository,
)
from app.modules.identity.authentication.infrastructure.unit_of_work import InMemoryUnitOfWork
from app.shared.domain.clock import FrozenClock
from app.shared.domain.errors import InfrastructureError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.uuid_provider import FixedUUIDProvider, StandardUUIDProvider

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_EMAIL = "alice@example.com"
_STRONG_PASSWORD = "CorrectHorseBatteryStaple!"
_WEAK_PASSWORD = "short"
_FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)

_USER_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
_SESSION_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")
_JTI_UUID = uuid.UUID("00000000-0000-4000-8000-000000000003")


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class StubPasswordHasher:
    """Always returns a fixed PasswordHash for any plaintext."""

    def hash(self, plain_password: str) -> PasswordHash:
        return PasswordHash(value="$argon2id$stub$hash")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        return True

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        return False


class FailingHasher:
    """Raises PasswordHashingError on hash() — simulates infrastructure failure."""

    def hash(self, plain_password: str) -> PasswordHash:
        raise PasswordHashingError("Argon2 context initialisation failed.")

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        return False

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


class FailingAuthRepo(InMemoryAuthRepository):
    """Raises InfrastructureError on save() to simulate DB write failure."""

    async def save(self, credential: AuthenticationCredential) -> None:
        raise Exception("DB connection reset by peer")


class StubRefreshTokenService:
    """Returns a fixed PlainRefreshToken and RefreshTokenId on issue()."""

    _PLAIN = PlainRefreshToken.generate()
    _ID = RefreshTokenId(uuid.UUID("ffffffff-0000-4000-8000-000000000001"))

    async def issue(self, *, session_id: Any, user_id: Any, expires_at: Any, **_: Any) -> Any:
        from app.shared.domain.result import Success

        return Success((self._PLAIN, self._ID))

    async def rotate(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_session(self, **_: Any) -> Any:
        raise NotImplementedError

    async def revoke_all_for_user(self, **_: Any) -> Any:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service(
    *,
    auth_repo: InMemoryAuthRepository | None = None,
    require_email_verification: bool = True,
    auto_verify_email: bool = False,
    create_session: bool = True,
    hasher: Any = None,
    event_publisher: StubEventPublisher | None = None,
    uuid_ids: list[uuid.UUID] | None = None,
) -> tuple[RegistrationService, InMemoryUnitOfWork, StubEventPublisher]:
    """
    Build a RegistrationService with controllable collaborators.

    Returns (service, uow, event_publisher) so tests can inspect state.
    """
    _auth_repo = auth_repo or InMemoryAuthRepository()
    _session_repo = InMemorySessionRepository()
    _token_store = InMemoryRefreshTokenStore()
    _refresh_svc = StubRefreshTokenService()
    _jwt_svc = StubJWTService()
    _hasher = hasher or StubPasswordHasher()
    _strength = DefaultPasswordStrengthPolicy(minimum_length=12, maximum_length=128)
    _session_policy = DefaultSessionPolicy(session_ttl_days=7)
    _auth_policy = DefaultAuthenticationPolicy(
        require_email_verification=require_email_verification
    )
    _uow = InMemoryUnitOfWork()
    _pub = event_publisher or StubEventPublisher()
    _uuid = FixedUUIDProvider(uuid_ids or [_USER_UUID, _SESSION_UUID, _JTI_UUID])
    _clock = FrozenClock(_FIXED_NOW)
    _config = RegistrationConfiguration(
        auto_verify_email=auto_verify_email,
        access_token_lifetime_minutes=15,
        jwt_issuer="https://api.travix.ai",
        jwt_audience="travix-mobile",
    )

    service = RegistrationService(
        auth_repository=_auth_repo,
        session_repository=_session_repo,
        refresh_token_service=_refresh_svc,
        jwt_service=_jwt_svc,
        password_hasher=_hasher,
        strength_policy=_strength,
        session_policy=_session_policy,
        auth_policy=_auth_policy,
        unit_of_work=_uow,
        event_publisher=_pub,
        uuid_provider=_uuid,
        clock=_clock,
        config=_config,
    )
    return service, _uow, _pub


# ---------------------------------------------------------------------------
# Scenario 1: Happy path with session (full flow)
# ---------------------------------------------------------------------------


class TestScenario1SuccessWithSession:
    async def test_returns_success(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        result = await service.execute(cmd)
        assert result.is_ok

    async def test_summary_fields(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        summary = (await service.execute(cmd)).unwrap()

        assert str(summary.email) == _VALID_EMAIL
        assert summary.session_created is True
        assert summary.session_id is not None
        assert summary.access_token is not None
        assert summary.plain_refresh_token is not None

    async def test_uow_committed(self) -> None:
        service, uow, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        await service.execute(cmd)
        assert uow.committed is True
        assert uow.rolled_back is False

    async def test_credential_persisted_in_repo(self) -> None:
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(auth_repo=repo)
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        await service.execute(cmd)
        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None

    async def test_user_registered_event_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        await service.execute(cmd)
        assert any(isinstance(e, UserRegistered) for e in pub.published)

    async def test_user_logged_in_event_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        await service.execute(cmd)
        assert any(isinstance(e, UserLoggedIn) for e in pub.published)

    async def test_access_token_contains_user_id(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        summary = (await service.execute(cmd)).unwrap()
        # StubJWTService embeds the sub (user_id) in the token string
        assert str(summary.user_id) in (summary.access_token or "")

    async def test_summary_repr_does_not_expose_tokens(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        summary = (await service.execute(cmd)).unwrap()
        rep = repr(summary)
        assert "test.access.token" not in rep
        assert "[REDACTED" in rep


# ---------------------------------------------------------------------------
# Scenario 2: Success without session (create_session=False)
# ---------------------------------------------------------------------------


class TestScenario2SuccessNoSession:
    async def test_returns_success(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        result = await service.execute(cmd)
        assert result.is_ok

    async def test_no_session_id_in_summary(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        summary = (await service.execute(cmd)).unwrap()
        assert summary.session_created is False
        assert summary.session_id is None
        assert summary.access_token is None
        assert summary.plain_refresh_token is None

    async def test_no_user_logged_in_event(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        assert not any(isinstance(e, UserLoggedIn) for e in pub.published)

    async def test_user_registered_event_still_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        assert any(isinstance(e, UserRegistered) for e in pub.published)

    async def test_uow_committed(self) -> None:
        service, uow, _ = _make_service()
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        assert uow.committed is True


# ---------------------------------------------------------------------------
# Scenario 3: Email already exists
# ---------------------------------------------------------------------------


class TestScenario3EmailAlreadyExists:
    async def test_returns_failure(self) -> None:
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(auth_repo=repo)

        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        await service.execute(cmd)  # first registration

        # Reset UUID provider for second call
        service2, _, _ = _make_service(auth_repo=repo)
        result = await service2.execute(cmd)

        assert not result.is_ok
        assert isinstance(result.error, EmailAlreadyExistsError)

    async def test_uow_not_committed(self) -> None:
        repo = InMemoryAuthRepository()
        service1, _, _ = _make_service(auth_repo=repo)
        await service1.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))

        service2, uow2, _ = _make_service(auth_repo=repo)
        await service2.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert uow2.committed is False

    async def test_no_events_published(self) -> None:
        repo = InMemoryAuthRepository()
        service1, _, _ = _make_service(auth_repo=repo)
        await service1.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))

        pub = StubEventPublisher()
        service2, _, _ = _make_service(auth_repo=repo, event_publisher=pub)
        await service2.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert pub.published == []

    async def test_case_insensitive_email_collision(self) -> None:
        repo = InMemoryAuthRepository()
        service1, _, _ = _make_service(auth_repo=repo)
        await service1.execute(RegisterUserCommand(email="Alice@Example.COM", password=_STRONG_PASSWORD))

        service2, _, _ = _make_service(auth_repo=repo)
        result = await service2.execute(
            RegisterUserCommand(email="alice@example.com", password=_STRONG_PASSWORD)
        )
        assert isinstance(result.error, EmailAlreadyExistsError)


# ---------------------------------------------------------------------------
# Scenario 4: Invalid email format
# ---------------------------------------------------------------------------


class TestScenario4InvalidEmail:
    @pytest.mark.parametrize(
        "bad_email",
        [
            "not-an-email",
            "missing@tld",
            "@nodomain.com",
            "spaces in@email.com",
            "",
            "a" * 300 + "@example.com",
        ],
    )
    async def test_returns_invalid_email_error(self, bad_email: str) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=bad_email, password=_STRONG_PASSWORD)
        result = await service.execute(cmd)
        assert not result.is_ok
        assert isinstance(result.error, InvalidEmailError)

    async def test_uow_never_entered(self) -> None:
        service, uow, _ = _make_service()
        cmd = RegisterUserCommand(email="bad@@email", password=_STRONG_PASSWORD)
        await service.execute(cmd)
        assert uow.committed is False
        assert uow.rolled_back is False

    async def test_no_events_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(event_publisher=pub)
        await service.execute(RegisterUserCommand(email="bad", password=_STRONG_PASSWORD))
        assert pub.published == []


# ---------------------------------------------------------------------------
# Scenario 5: Weak password
# ---------------------------------------------------------------------------


class TestScenario5WeakPassword:
    async def test_returns_weak_password_error(self) -> None:
        service, _, _ = _make_service()
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_WEAK_PASSWORD)
        result = await service.execute(cmd)
        assert not result.is_ok
        assert isinstance(result.error, WeakPasswordError)

    async def test_violations_list_is_non_empty(self) -> None:
        service, _, _ = _make_service()
        result = await service.execute(
            RegisterUserCommand(email=_VALID_EMAIL, password="ab")
        )
        assert isinstance(result.error, WeakPasswordError)
        assert len(result.error.violations) > 0

    async def test_uow_never_entered(self) -> None:
        service, uow, _ = _make_service()
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password="short"))
        assert uow.committed is False
        assert uow.rolled_back is False

    async def test_credential_not_persisted(self) -> None:
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(auth_repo=repo)
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password="short"))
        assert repo.count() == 0


# ---------------------------------------------------------------------------
# Scenario 6: Hash failure
# ---------------------------------------------------------------------------


class TestScenario6HashFailure:
    async def test_returns_password_hashing_error(self) -> None:
        service, _, _ = _make_service(hasher=FailingHasher())
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        result = await service.execute(cmd)
        assert not result.is_ok
        assert isinstance(result.error, PasswordHashingError)

    async def test_uow_never_committed(self) -> None:
        service, uow, _ = _make_service(hasher=FailingHasher())
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert uow.committed is False

    async def test_credential_not_persisted(self) -> None:
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(auth_repo=repo, hasher=FailingHasher())
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert repo.count() == 0

    async def test_no_events_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(hasher=FailingHasher(), event_publisher=pub)
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert pub.published == []


# ---------------------------------------------------------------------------
# Scenario 7: Persistence failure (DB write error)
# ---------------------------------------------------------------------------


class TestScenario7PersistenceFailure:
    async def test_returns_infrastructure_error(self) -> None:
        service, _, _ = _make_service(auth_repo=FailingAuthRepo())
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        result = await service.execute(cmd)
        assert not result.is_ok
        assert isinstance(result.error, InfrastructureError)

    async def test_uow_rolled_back(self) -> None:
        service, uow, _ = _make_service(auth_repo=FailingAuthRepo())
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert uow.committed is False
        assert uow.rolled_back is True

    async def test_no_events_published(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(auth_repo=FailingAuthRepo(), event_publisher=pub)
        await service.execute(RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD))
        assert pub.published == []


# ---------------------------------------------------------------------------
# Scenario 8: Email verification required (production path)
# ---------------------------------------------------------------------------


class TestScenario8EmailVerificationRequired:
    async def test_email_not_verified_in_summary(self) -> None:
        service, _, _ = _make_service(
            require_email_verification=True, auto_verify_email=False
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        summary = (await service.execute(cmd)).unwrap()
        assert summary.is_email_verified is False
        assert summary.requires_email_verification is True

    async def test_email_verification_requested_event_emitted(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=True,
            auto_verify_email=False,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        evts = pub.events_of_type(EmailVerificationRequested)
        assert len(evts) == 1
        assert evts[0].email == _VALID_EMAIL

    async def test_no_user_email_auto_verified_event(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=True,
            auto_verify_email=False,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        assert not any(isinstance(e, UserEmailAutoVerified) for e in pub.published)

    async def test_credential_persisted_with_unverified_email(self) -> None:
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(
            auth_repo=repo,
            require_email_verification=True,
            auto_verify_email=False,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        stored = await repo.find_by_email(Email(_VALID_EMAIL))
        assert stored is not None
        assert stored.is_email_verified is False


# ---------------------------------------------------------------------------
# Scenario 9: Dev-mode auto-verification (config-driven)
# ---------------------------------------------------------------------------


class TestScenario9DevModeAutoVerification:
    async def test_email_is_verified_in_summary(self) -> None:
        service, _, _ = _make_service(
            require_email_verification=True, auto_verify_email=True
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        summary = (await service.execute(cmd)).unwrap()
        assert summary.is_email_verified is True
        assert summary.requires_email_verification is False

    async def test_user_email_auto_verified_event_emitted(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=True,
            auto_verify_email=True,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        evts = pub.events_of_type(UserEmailAutoVerified)
        assert len(evts) == 1
        assert evts[0].email == _VALID_EMAIL

    async def test_no_email_verification_requested_event(self) -> None:
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=True,
            auto_verify_email=True,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        await service.execute(cmd)
        assert not any(isinstance(e, EmailVerificationRequested) for e in pub.published)

    async def test_auto_verify_false_does_not_verify(self) -> None:
        """Guard: auto_verify_email=False must NOT mark email as verified."""
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=True,
            auto_verify_email=False,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        summary = (await service.execute(cmd)).unwrap()
        assert summary.is_email_verified is False
        assert not any(isinstance(e, UserEmailAutoVerified) for e in pub.published)

    async def test_policy_no_verification_auto_verifies_silently(self) -> None:
        """When policy requires no verification, email is verified regardless of config."""
        pub = StubEventPublisher()
        service, _, _ = _make_service(
            require_email_verification=False,
            auto_verify_email=False,
            event_publisher=pub,
        )
        cmd = RegisterUserCommand(
            email=_VALID_EMAIL, password=_STRONG_PASSWORD, create_session=False
        )
        summary = (await service.execute(cmd)).unwrap()
        assert summary.is_email_verified is True
        # Neither event should be emitted — silent auto-verify
        assert not any(isinstance(e, UserEmailAutoVerified) for e in pub.published)
        assert not any(isinstance(e, EmailVerificationRequested) for e in pub.published)


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------


class TestSecurityInvariants:
    async def test_command_repr_redacts_password(self) -> None:
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password="super-secret-password")
        assert "super-secret-password" not in repr(cmd)
        assert "[REDACTED]" in repr(cmd)

    async def test_command_str_redacts_password(self) -> None:
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password="my-password")
        assert "my-password" not in str(cmd)

    async def test_summary_repr_does_not_expose_access_token(self) -> None:
        service, _, _ = _make_service()
        summary = (
            await service.execute(
                RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
            )
        ).unwrap()
        assert summary.access_token is not None  # token was issued
        assert summary.access_token not in repr(summary)

    async def test_summary_repr_does_not_expose_refresh_token_value(self) -> None:
        service, _, _ = _make_service()
        summary = (
            await service.execute(
                RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
            )
        ).unwrap()
        token = summary.plain_refresh_token
        assert token is not None
        assert token.as_client_token() not in repr(summary)

    async def test_password_not_in_credential(self) -> None:
        """The credential must never store the plaintext password."""
        repo = InMemoryAuthRepository()
        service, _, _ = _make_service(auth_repo=repo)
        await service.execute(
            RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        )
        credential = await repo.find_by_email(Email(_VALID_EMAIL))
        assert credential is not None
        assert _STRONG_PASSWORD not in credential.password_hash.value


# ---------------------------------------------------------------------------
# RegisterUserHandler
# ---------------------------------------------------------------------------


class TestRegisterUserHandler:
    async def test_handler_delegates_to_service(self) -> None:
        from app.modules.identity.authentication.application.registration_handler import (
            RegisterUserHandler,
        )

        service, _, _ = _make_service()
        handler = RegisterUserHandler(service=service)
        cmd = RegisterUserCommand(email=_VALID_EMAIL, password=_STRONG_PASSWORD)
        result = await handler.handle(cmd)
        assert result.is_ok

    async def test_handler_propagates_failure(self) -> None:
        from app.modules.identity.authentication.application.registration_handler import (
            RegisterUserHandler,
        )

        service, _, _ = _make_service()
        handler = RegisterUserHandler(service=service)
        cmd = RegisterUserCommand(email="not-an-email", password=_STRONG_PASSWORD)
        result = await handler.handle(cmd)
        assert not result.is_ok
        assert isinstance(result.error, InvalidEmailError)
