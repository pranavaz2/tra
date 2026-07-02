"""
Registration Application Service.

Orchestrates the full user registration workflow, coordinating:
  - Email format validation (Email value object)
  - Email uniqueness check (AuthenticationRepository)
  - Password strength validation (PasswordStrengthPolicy)
  - Password hashing (PasswordHasher, via thread pool — CPU-bound)
  - Credential creation (AuthenticationCredential aggregate)
  - Email verification workflow (event emission, config-driven auto-verify)
  - Optional session creation (AuthenticationSession + JWT + refresh token)
  - Atomic persistence (Unit of Work)
  - Domain event publication (EventPublisher, after commit)

Architecture constraints:
  - NO FastAPI imports. This module has zero web-framework dependencies.
  - NO SQLAlchemy imports. All persistence goes through repository interfaces.
  - NO HTTP exceptions. Failures are returned as Failure(TravixError).
  - Business logic lives here, not in the API layer.
  - The domain layer is UNCHANGED — this service only orchestrates domain objects.

Transaction guarantee:
  All repository mutations (credential + optional session) are committed in
  a single Unit of Work. A failure at any point causes a full rollback.
  Domain events are published only AFTER a successful commit.

Sensitive data policy (CLAUDE.md §15 rule 4):
  NEVER log: password, password_hash, access_token, refresh_token.
  User IDs and email domain suffix are safe for structured logs.
  Command repr is safe to log (password field is [REDACTED]).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from app.core.security.jwt.claims import AccessTokenClaims
from app.core.security.jwt.interfaces import JWTService
from app.modules.identity.authentication.application.commands import RegisterUserCommand
from app.modules.identity.authentication.application.dtos import (
    RegistrationResult,
    RegistrationSummary,
)
from app.modules.identity.authentication.application.interfaces import RefreshTokenService
from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.errors import (
    EmailAlreadyExistsError,
    PasswordHashingError,
    WeakPasswordError,
)
from app.modules.identity.authentication.domain.events.authentication_events import (
    EmailVerificationRequested,
    UserEmailAutoVerified,
)
from app.modules.identity.authentication.domain.repositories.interfaces import (
    AuthenticationRepository,
    SessionRepository,
)
from app.modules.identity.authentication.domain.services.password_hasher import PasswordHasher
from app.modules.identity.authentication.domain.services.password_policies import (
    PasswordStrengthPolicy,
)
from app.modules.identity.authentication.domain.services.policies import (
    AuthenticationPolicy,
    SessionPolicy,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.shared.domain.clock import Clock
from app.shared.domain.errors import InfrastructureError, TravixError
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

logger = logging.getLogger(__name__)

# Sentinel for _SessionResult unpacking
_SessionResult = tuple[AuthenticationSession, PlainRefreshToken, str]


@dataclass(frozen=True)
class RegistrationConfiguration:
    """
    Configuration values consumed by RegistrationService.

    Created by the DI layer (infrastructure/dependencies.py) from
    application Settings. Keeps the service decoupled from Settings
    and from os.environ.

    Attributes:
        auto_verify_email:             When True, skip the email verification
                                       round-trip and mark the credential
                                       verified immediately. Driven by
                                       settings.registration_auto_verify_email.
                                       MUST be False in production.
        access_token_lifetime_minutes: JWT access token TTL (from JWT settings).
        jwt_issuer:                    Token issuer claim (from JWT settings).
        jwt_audience:                  Token audience claim (from JWT settings).
    """

    auto_verify_email: bool = False
    access_token_lifetime_minutes: int = 15
    jwt_issuer: str = "https://api.travix.ai"
    jwt_audience: str = "travix-mobile"


class RegistrationService:
    """
    Orchestrates new user registration from command to persisted result.

    All dependencies are injected via the constructor. No concrete
    infrastructure types are imported here — only domain and shared-kernel
    interfaces (protocols and frozen dataclasses).

    Domain scenarios handled:
      1. Success with session (full happy path)
      2. Success without session (create_session=False)
      3. Email already exists            → Failure(EmailAlreadyExistsError)
      4. Invalid email format            → Failure(InvalidEmailError)
      5. Weak password                   → Failure(WeakPasswordError)
      6. Hash failure                    → Failure(PasswordHashingError)
      7. Persistence failure             → Failure(InfrastructureError)
      8. Email verification required     → EmailVerificationRequested event emitted
      9. Dev-mode auto-verification      → credential verified + UserEmailAutoVerified
    """

    def __init__(
        self,
        *,
        auth_repository: AuthenticationRepository,
        session_repository: SessionRepository,
        refresh_token_service: RefreshTokenService,
        jwt_service: JWTService,
        password_hasher: PasswordHasher,
        strength_policy: PasswordStrengthPolicy,
        session_policy: SessionPolicy,
        auth_policy: AuthenticationPolicy,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
        config: RegistrationConfiguration,
    ) -> None:
        self._auth_repo = auth_repository
        self._session_repo = session_repository
        self._refresh_token_service = refresh_token_service
        self._jwt_service = jwt_service
        self._hasher = password_hasher
        self._strength_policy = strength_policy
        self._session_policy = session_policy
        self._auth_policy = auth_policy
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid = uuid_provider
        self._clock = clock
        self._config = config

    async def execute(self, command: RegisterUserCommand) -> RegistrationResult:
        """
        Execute the registration command and return a typed Result.

        Never raises for expected failures — all expected outcomes are
        wrapped in Failure(TravixError). Unexpected infrastructure errors
        are caught, logged, and wrapped in Failure(InfrastructureError).

        Returns:
            Success(RegistrationSummary)     — registration succeeded.
            Failure(InvalidEmailError)       — email format is invalid.
            Failure(EmailAlreadyExistsError) — email already registered.
            Failure(WeakPasswordError)       — password fails strength policy.
            Failure(PasswordHashingError)    — hashing subsystem failure.
            Failure(InfrastructureError)     — database or token-service failure.
        """
        logger.info("Registration attempt", extra={"email_domain": _email_domain(command.email)})

        # ------------------------------------------------------------------ #
        # Step 1: Validate email format (pure — no I/O)                       #
        # ------------------------------------------------------------------ #
        try:
            email = Email(command.email)
        except TravixError as e:
            return Failure(e)
        except Exception as e:
            return Failure(InfrastructureError("Email validation failed unexpectedly.", cause=e))

        # ------------------------------------------------------------------ #
        # Step 2: Check email uniqueness (read-only, outside UoW)             #
        # ------------------------------------------------------------------ #
        try:
            already_exists = await self._auth_repo.exists_with_email(email)
        except Exception as e:
            logger.error("Email uniqueness check failed", extra={"reason": str(e)})
            return Failure(InfrastructureError("Registration failed: storage unavailable.", cause=e))

        if already_exists:
            logger.info(
                "Registration rejected: email already registered",
                extra={"email_domain": _email_domain(command.email)},
            )
            return Failure(EmailAlreadyExistsError())

        # ------------------------------------------------------------------ #
        # Step 3: Validate password strength (pure — no I/O)                  #
        # ------------------------------------------------------------------ #
        violations = self._strength_policy.get_violations(command.password)
        if violations:
            return Failure(WeakPasswordError(violations=violations))

        # ------------------------------------------------------------------ #
        # Step 4: Hash password (CPU-bound — offload to thread pool)          #
        # ------------------------------------------------------------------ #
        try:
            password_hash = await asyncio.to_thread(self._hasher.hash, command.password)
        except PasswordHashingError as e:
            logger.error("Password hashing failed", extra={"reason": e.code})
            return Failure(e)
        except Exception as e:
            logger.error("Unexpected error during password hashing", extra={"reason": str(e)})
            return Failure(PasswordHashingError("Password hashing failed.", cause=e))

        # ------------------------------------------------------------------ #
        # Step 5: Create credential aggregate (pure — no I/O)                 #
        # ------------------------------------------------------------------ #
        user_id = UserId(self._uuid.generate())
        credential = AuthenticationCredential.create(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
        )

        # ------------------------------------------------------------------ #
        # Steps 6–8: Atomic Unit of Work                                       #
        # ------------------------------------------------------------------ #
        session: AuthenticationSession | None = None
        plain_refresh_token: PlainRefreshToken | None = None
        access_token: str | None = None
        # Integration events the service emits directly — not via aggregate.push_event(),
        # because EmailVerificationRequested and UserEmailAutoVerified are application-level
        # signals, not aggregate-internal state-change events.
        service_events: list[DomainEvent] = []

        try:
            async with self._uow:
                # Step 6: Persist credential
                await self._auth_repo.save(credential)

                # Step 7: Handle email verification
                # Returns integration events without touching the aggregate's internal
                # _pending_events list — respecting the aggregate boundary.
                service_events = self._apply_verification(credential, email)

                # Step 8: Optional session creation
                if command.create_session:
                    session, plain_refresh_token, access_token = await self._create_session(
                        command, user_id, email, credential
                    )

                # All mutations succeeded — commit atomically
                await self._uow.commit()

        except TravixError as e:
            logger.error(
                "Registration failed within UoW",
                extra={"reason": e.code, "user_id": str(user_id)},
            )
            return Failure(e)
        except Exception as e:
            logger.error(
                "Registration persistence failed",
                extra={"reason": str(e), "user_id": str(user_id)},
            )
            return Failure(InfrastructureError("Registration failed due to a storage error.", cause=e))

        # ------------------------------------------------------------------ #
        # Step 9: Publish domain events (only after successful commit)         #
        # ------------------------------------------------------------------ #
        # Aggregate-internal events (UserRegistered, UserLoggedIn) plus service-
        # level integration events (EmailVerificationRequested / UserEmailAutoVerified).
        events = [*credential.pop_events(), *service_events]
        if session is not None:
            events = [*events, *session.pop_events()]

        if events:
            try:
                await self._event_publisher.publish(events)
            except Exception as e:
                # Best-effort: a publish failure must NOT appear to roll back
                # the already-committed write. Log and continue.
                logger.error(
                    "Event publication failed after successful registration",
                    extra={"event_count": len(events), "reason": str(e)},
                )

        logger.info(
            "Registration succeeded",
            extra={
                "user_id": str(user_id),
                "session_created": session is not None,
                "is_email_verified": credential.is_email_verified,
            },
        )

        return Success(
            RegistrationSummary(
                user_id=user_id,
                email=email,
                is_email_verified=credential.is_email_verified,
                session_created=session is not None,
                requires_email_verification=(
                    self._auth_policy.require_email_verification
                    and not credential.is_email_verified
                ),
                session_id=session.session_id if session is not None else None,
                access_token=access_token,
                plain_refresh_token=plain_refresh_token,
            )
        )

    # ---------------------------------------------------------------------- #
    # Private helpers                                                          #
    # ---------------------------------------------------------------------- #

    def _apply_verification(
        self,
        credential: AuthenticationCredential,
        email: Email,
    ) -> list[DomainEvent]:
        """
        Apply the email verification strategy for a newly created credential.

        Returns a list of integration events to be published after UoW commit.
        Does NOT call credential.push_event() — that method is reserved for
        intra-aggregate state transitions, not service-level signals.

        Three paths, in priority order:
          A. Policy does not require verification → auto-verify silently, no event.
             Used for internal tooling, SSO-backed flows, etc.
          B. Config enables auto-verify (dev/test) → verify + return audit event.
             MUST be False in production (guarded by config, not by code).
          C. Production → return EmailVerificationRequested for the notification
             service to handle email dispatch.
        """
        if not self._auth_policy.require_email_verification:
            credential.verify_email()
            return []

        if self._config.auto_verify_email:
            credential.verify_email()
            return [
                UserEmailAutoVerified(
                    aggregate_id=str(credential.user_id),
                    user_id=str(credential.user_id),
                    email=str(email),
                )
            ]

        # Production path: notification service handles email dispatch.
        return [
            EmailVerificationRequested(
                aggregate_id=str(credential.user_id),
                user_id=str(credential.user_id),
                email=str(email),
            )
        ]

    async def _create_session(
        self,
        command: RegisterUserCommand,
        user_id: UserId,
        email: Email,
        credential: AuthenticationCredential,
    ) -> _SessionResult:
        """
        Create a session, issue a refresh token, and sign an access token.

        This helper runs inside the Unit of Work context. Any raised
        TravixError propagates to the UoW `async with` block, which
        rolls back the transaction and re-raises for the outer handler.

        Returns:
            (session, plain_refresh_token, access_token_str)

        Raises:
            TravixError subclass on any expected failure (triggers UoW rollback).
            Exception on unexpected infrastructure failure.
        """
        session_id = SessionId(self._uuid.generate())
        expires_at = self._clock.now() + self._session_policy.session_ttl

        # Issue the refresh token (generates + persists the record)
        refresh_result = await self._refresh_token_service.issue(
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            device_id=command.device_id,
            device_name=command.device_name,
            platform=command.platform,
        )
        if not refresh_result.is_ok:
            raise refresh_result.error  # triggers UoW rollback

        plain_token, refresh_token_id = refresh_result.value

        # Create session aggregate (emits UserLoggedIn domain event)
        session = AuthenticationSession.create(
            session_id=session_id,
            user_id=user_id,
            refresh_token_id=refresh_token_id,
            expires_at=expires_at,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._session_repo.save(session)

        # Sign the access token (synchronous — CPU-bound via PyJWT)
        now = self._clock.now()
        exp = now + timedelta(minutes=self._config.access_token_lifetime_minutes)
        claims = AccessTokenClaims(
            sub=str(user_id),
            jti=str(self._uuid.generate()),
            iat=now,
            exp=exp,
            nbf=now,
            iss=self._config.jwt_issuer,
            aud=self._config.jwt_audience,
            sid=str(session_id),
            email=str(email),
            verified=credential.is_email_verified,
        )
        access_token = self._jwt_service.create_access_token(claims)

        return session, plain_token, access_token


def _email_domain(raw_email: str) -> str:
    """Extract only the domain part of an email for safe structured log output."""
    parts = raw_email.split("@", 1)
    return parts[1] if len(parts) == 2 else "<unknown>"  # noqa: PLR2004
