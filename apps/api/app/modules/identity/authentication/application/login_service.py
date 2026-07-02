"""
Login Application Service.

Orchestrates the full password-based user authentication workflow, coordinating:
  - Email format validation (Email value object)
  - Credential lookup (AuthenticationRepository)
  - Constant-time response for unknown email (prevents enumeration)
  - Account state checks (disabled, locked, email unverified)
  - Optional risk assessment (RiskAssessmentService — no implementation required)
  - Password verification (PasswordHasher.verify, via thread pool — CPU-bound)
  - Failed login recording (separate mini-UoW — best-effort, non-blocking)
  - Transparent password rehash if algorithm parameters changed (needs_rehash)
  - Successful login recording (record_successful_login clears lockout)
  - Session creation (AuthenticationSession aggregate)
  - Refresh token issuance (RefreshTokenService)
  - JWT access token signing (JWTService)
  - Atomic persistence (Unit of Work — success path only)
  - Domain event publication (EventPublisher, after commit)

Architecture constraints:
  - NO FastAPI imports. This module has zero web-framework dependencies.
  - NO SQLAlchemy imports. All persistence goes through repository interfaces.
  - NO HTTP exceptions. Failures are returned as Failure(TravixError).
  - Business logic lives here, not in the API layer.
  - The domain layer is UNCHANGED — this service only orchestrates domain objects.
    (Entities are mutated only via their own methods, except for transparent
    password rehash which sets credential.password_hash directly to avoid
    the side effects of change_password(): wrong password_changed_at timestamp
    and spurious PasswordChanged event.)

Transaction guarantee:
  The FAILED LOGIN path uses an isolated mini-UoW (record_failed_login +
  auth_repo.save). Failure to persist the counter is logged but does not
  change the HTTP response — the caller still receives InvalidCredentialsError.

  The SUCCESS path uses the main UoW: record_successful_login + optional rehash
  + session + refresh token + auth_repo.save + session_repo.save + uow.commit().
  A failure at any point causes a full rollback.

  Domain events are published only AFTER a successful commit.

Timing attack prevention:
  "Email not found" and "wrong password" MUST return in the same time as a
  valid verification attempt. We achieve this by running the full Argon2
  verify() operation even when the email is unknown (against a cached dummy
  hash). Without this, an attacker can enumerate valid email addresses by
  measuring response times.

Sensitive data policy (CLAUDE.md §11):
  NEVER log: password, password_hash, access_token, refresh_token, full email.
  Safe to log: email domain suffix, user_id (after authentication), session_id,
  error codes, boolean flags (is_email_verified, session_created).
  Command repr is safe to log (password field is [REDACTED]).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.security.jwt.claims import AccessTokenClaims
from app.core.security.jwt.interfaces import JWTService
from app.modules.identity.authentication.application.commands import LoginUserCommand
from app.modules.identity.authentication.application.dtos import (
    AuthenticatedSessionSummary,
    LoginResult,
)
from app.modules.identity.authentication.application.interfaces import (
    RefreshTokenService,
    RiskAction,
    RiskAssessmentService,
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
)
from app.modules.identity.authentication.domain.repositories.interfaces import (
    AuthenticationRepository,
    SessionRepository,
)
from app.modules.identity.authentication.domain.services.password_hasher import PasswordHasher
from app.modules.identity.authentication.domain.services.policies import (
    AuthenticationPolicy,
    SessionPolicy,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash
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

# Internal tuple returned by _create_session helper
_SessionResult = tuple[AuthenticationSession, PlainRefreshToken, str]


@dataclass(frozen=True)
class LoginConfiguration:
    """
    Configuration values consumed by LoginService.

    Created by the DI layer (infrastructure/dependencies.py) from application
    Settings. Keeps the service decoupled from Settings and from os.environ.

    Attributes:
        access_token_lifetime_minutes: JWT access token TTL in minutes.
        jwt_issuer:                    Token issuer claim (iss).
        jwt_audience:                  Token audience claim (aud).
    """

    access_token_lifetime_minutes: int = 15
    jwt_issuer: str = "https://api.travix.ai"
    jwt_audience: str = "travix-mobile"


class LoginService:
    """
    Orchestrates password-based user authentication from command to persisted result.

    All dependencies are injected via the constructor. No concrete infrastructure
    types are imported — only domain and shared-kernel interfaces.

    Domain scenarios handled:
      1.  Valid credentials, active account           → Success(AuthenticatedSessionSummary)
      2.  Email not found                             → constant-time dummy verify
                                                        → Failure(InvalidCredentialsError)
      3.  Wrong password                              → record_failed_login (mini-UoW)
                                                        → Failure(InvalidCredentialsError)
      4.  Account disabled                            → Failure(AccountDisabledError)
      5.  Account locked                              → Failure(AccountLockedError)
      6.  Email not verified (if policy requires)     → Failure(EmailNotVerifiedError)
      7.  Transparent password rehash                 → updates hash silently, emits
                                                        PasswordRehashed (service event)
      8.  Refresh token issued                        → via RefreshTokenService.issue()
      9.  JWT access token signed                     → via JWTService.create_access_token()
      10. Session created                             → AuthenticationSession.create()
      11. Persistence failure on success path         → rollback → Failure(InfrastructureError)
    """

    def __init__(
        self,
        *,
        auth_repository: AuthenticationRepository,
        session_repository: SessionRepository,
        refresh_token_service: RefreshTokenService,
        jwt_service: JWTService,
        password_hasher: PasswordHasher,
        session_policy: SessionPolicy,
        auth_policy: AuthenticationPolicy,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
        config: LoginConfiguration,
        risk_service: RiskAssessmentService | None = None,
    ) -> None:
        self._auth_repo = auth_repository
        self._session_repo = session_repository
        self._refresh_token_service = refresh_token_service
        self._jwt_service = jwt_service
        self._hasher = password_hasher
        self._session_policy = session_policy
        self._auth_policy = auth_policy
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid = uuid_provider
        self._clock = clock
        self._config = config
        self._risk_service = risk_service
        # Lazily initialised constant-time dummy hash (see _equalize_timing).
        # One-time cost: computed on the first login attempt where email is unknown.
        self._dummy_hash: PasswordHash | None = None

    async def execute(self, command: LoginUserCommand) -> LoginResult:
        """
        Execute a login command and return a typed Result.

        Never raises for expected failures. All expected outcomes are wrapped in
        Failure(TravixError). Unexpected infrastructure errors are caught, logged,
        and wrapped in Failure(InfrastructureError).

        Returns:
            Success(AuthenticatedSessionSummary) — login succeeded.
            Failure(InvalidCredentialsError)     — wrong password or unknown email.
            Failure(AccountDisabledError)        — account permanently deactivated.
            Failure(AccountLockedError)          — account temporarily locked.
            Failure(EmailNotVerifiedError)       — email verification required.
            Failure(AuthenticationFailedError)   — blocked by risk assessment.
            Failure(PasswordHashingError)        — hashing subsystem failure.
            Failure(InfrastructureError)         — database or token-service failure.
        """
        logger.info(
            "Login attempt",
            extra={"email_domain": _email_domain(command.email), "ip": command.ip_address},
        )

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
        # Step 2: Load credential by email (read — outside UoW)               #
        # ------------------------------------------------------------------ #
        try:
            credential = await self._auth_repo.find_by_email(email)
        except Exception as e:
            logger.error("Credential lookup failed", extra={"reason": str(e)})
            return Failure(InfrastructureError("Login failed: storage unavailable.", cause=e))

        # ------------------------------------------------------------------ #
        # Step 3: Constant-time guard for unknown email                        #
        # ------------------------------------------------------------------ #
        if credential is None:
            # Run a full Argon2 verify against a cached dummy hash so that
            # "email not found" takes the same wall-clock time as "wrong password".
            # Without this, response time difference reveals whether an email exists.
            await self._equalize_timing(command.password)
            await self._publish_failed_attempt(
                failure_reason="invalid_credentials",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                user_id=None,
            )
            return Failure(InvalidCredentialsError())

        # ------------------------------------------------------------------ #
        # Step 4: Account state checks (pure — no I/O, ordered by severity)   #
        # ------------------------------------------------------------------ #
        if not credential.is_active:
            await self._publish_failed_attempt(
                failure_reason="account_disabled",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                user_id=str(credential.user_id),
            )
            return Failure(AccountDisabledError())

        if credential.is_locked:
            await self._publish_failed_attempt(
                failure_reason="account_locked",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                user_id=str(credential.user_id),
            )
            return Failure(AccountLockedError(locked_until=credential.locked_until))

        if self._auth_policy.require_email_verification and not credential.is_email_verified:
            await self._publish_failed_attempt(
                failure_reason="email_not_verified",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                user_id=str(credential.user_id),
            )
            return Failure(EmailNotVerifiedError())

        # ------------------------------------------------------------------ #
        # Step 5: Risk assessment (optional insertion point)                   #
        # ------------------------------------------------------------------ #
        # When risk_service is None (default), login proceeds as ALLOW.
        # Inserting a concrete RiskAssessmentService requires only DI wiring —
        # no changes to this method.
        if self._risk_service is not None:
            try:
                risk = await self._risk_service.assess(
                    user_id=str(credential.user_id),
                    email=str(email),
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                    device_id=command.device_id,
                )
            except Exception as e:
                # Risk service failure must not block login (fail open).
                logger.error(
                    "Risk assessment failed — proceeding as ALLOW",
                    extra={"reason": str(e), "user_id": str(credential.user_id)},
                )
                risk = None

            if risk is not None and risk.action == RiskAction.BLOCK:
                logger.warning(
                    "Login blocked by risk assessment",
                    extra={
                        "user_id": str(credential.user_id),
                        "reason": risk.reason,
                        "risk_score": risk.risk_score,
                    },
                )
                await self._publish_failed_attempt(
                    failure_reason="risk_blocked",
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                    user_id=str(credential.user_id),
                )
                return Failure(
                    AuthenticationFailedError("Login blocked due to security policy.")
                )
            # RiskAction.CHALLENGE is deferred to TASK-2.x (step-up / MFA).

        # ------------------------------------------------------------------ #
        # Step 6: Verify password (CPU-bound — off-loaded to thread pool)      #
        # ------------------------------------------------------------------ #
        try:
            is_valid = await asyncio.to_thread(
                self._hasher.verify, command.password, credential.password_hash
            )
        except PasswordHashingError as e:
            logger.error("Password verification infrastructure failure", extra={"reason": e.code})
            return Failure(e)
        except Exception as e:
            logger.error(
                "Unexpected error during password verification", extra={"reason": str(e)}
            )
            return Failure(PasswordHashingError("Password verification failed.", cause=e))

        if not is_valid:
            # Persist failed attempt in an isolated mini-transaction (best-effort).
            await self._record_failed_attempt(credential)
            await self._publish_failed_attempt(
                failure_reason="invalid_credentials",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                user_id=str(credential.user_id),
            )
            return Failure(InvalidCredentialsError())

        # ------------------------------------------------------------------ #
        # Steps 7–10: Atomic success path (main Unit of Work)                  #
        # ------------------------------------------------------------------ #
        service_events: list[DomainEvent] = []
        session: AuthenticationSession | None = None
        plain_refresh_token: PlainRefreshToken | None = None
        access_token: str | None = None
        refresh_token_expires_at = self._clock.now() + self._session_policy.session_ttl

        try:
            async with self._uow:
                # Record successful login (clears lockout, updates last_login_at)
                credential.record_successful_login()

                # Transparent password rehash when algorithm / parameters are outdated
                if self._hasher.needs_rehash(credential.password_hash):
                    new_hash = await asyncio.to_thread(self._hasher.hash, command.password)
                    # Direct field mutation — bypasses change_password() deliberately:
                    #   (a) change_password() updates password_changed_at, which would
                    #       reset the PasswordExpiryPolicy baseline incorrectly.
                    #   (b) change_password() emits PasswordChanged, which would trigger
                    #       spurious "your password was changed" security notifications.
                    credential.password_hash = new_hash
                    credential.touch()
                    service_events.append(
                        PasswordRehashed(
                            aggregate_id=str(credential.user_id),
                            user_id=str(credential.user_id),
                        )
                    )

                await self._auth_repo.save(credential)

                # Create session, issue refresh token, sign JWT
                session, plain_refresh_token, access_token = await self._create_session(
                    command=command,
                    user_id=credential.user_id,
                    email=email,
                    is_email_verified=credential.is_email_verified,
                    refresh_token_expires_at=refresh_token_expires_at,
                )

                await self._uow.commit()

        except TravixError as e:
            logger.error(
                "Login failed within UoW",
                extra={"reason": e.code, "user_id": str(credential.user_id)},
            )
            return Failure(e)
        except Exception as e:
            logger.error(
                "Login persistence failed",
                extra={"reason": str(e), "user_id": str(credential.user_id)},
            )
            return Failure(InfrastructureError("Login failed due to a storage error.", cause=e))

        # ------------------------------------------------------------------ #
        # Step 11: Publish domain events (only after successful commit)         #
        # ------------------------------------------------------------------ #
        assert session is not None  # always set when UoW block succeeds
        assert plain_refresh_token is not None
        assert access_token is not None

        all_events: list[DomainEvent] = [
            *credential.pop_events(),
            *service_events,
            *session.pop_events(),
        ]
        if all_events:
            try:
                await self._event_publisher.publish(all_events)
            except Exception as e:
                # Best-effort: publish failure must not appear to roll back the commit.
                logger.error(
                    "Event publication failed after successful login",
                    extra={"event_count": len(all_events), "reason": str(e)},
                )

        now = self._clock.now()
        access_token_expires_at = now + timedelta(
            minutes=self._config.access_token_lifetime_minutes
        )

        logger.info(
            "Login succeeded",
            extra={
                "user_id": str(credential.user_id),
                "session_id": str(session.session_id),
                "is_email_verified": credential.is_email_verified,
            },
        )

        return Success(
            AuthenticatedSessionSummary(
                user_id=credential.user_id,
                email=email,
                session_id=session.session_id,
                access_token=access_token,
                plain_refresh_token=plain_refresh_token,
                access_token_expires_at=access_token_expires_at,
                refresh_token_expires_at=refresh_token_expires_at,
                is_email_verified=credential.is_email_verified,
            )
        )

    # ---------------------------------------------------------------------- #
    # Private helpers                                                          #
    # ---------------------------------------------------------------------- #

    async def _equalize_timing(self, plaintext: str) -> None:
        """
        Run a dummy Argon2 verify when the email is not found.

        Prevents timing-based email enumeration: without this, a response for
        an unknown email returns faster (no hash to verify) than for a wrong
        password (Argon2 dominates latency at ~100–300ms).

        The dummy hash is computed once and cached on the service instance. The
        one-time cost is paid on the first login attempt where email is unknown.
        """
        if self._dummy_hash is None:
            self._dummy_hash = await asyncio.to_thread(
                self._hasher.hash, "__travix_timing_equalization_constant__"
            )
        try:
            await asyncio.to_thread(self._hasher.verify, plaintext, self._dummy_hash)
        except Exception:
            pass  # Result and exceptions are irrelevant; equalization is the goal.

    async def _record_failed_attempt(self, credential: AuthenticationCredential) -> None:
        """
        Persist a failed login attempt in an isolated mini-transaction.

        Best-effort: a storage failure here does NOT change the HTTP response.
        The caller still receives InvalidCredentialsError. We log the failure
        for operational awareness but do not surface it to the user.
        """
        try:
            async with self._uow:
                credential.record_failed_login(
                    max_attempts=self._auth_policy.max_failed_attempts,
                    lockout_duration=self._auth_policy.lockout_duration,
                )
                await self._auth_repo.save(credential)
                await self._uow.commit()
        except Exception as e:
            logger.error(
                "Failed to persist failed login attempt",
                extra={"user_id": str(credential.user_id), "reason": str(e)},
            )

    async def _publish_failed_attempt(
        self,
        *,
        failure_reason: str,
        ip_address: str | None,
        user_agent: str | None,
        user_id: str | None,
    ) -> None:
        """
        Publish a LoginAttemptFailed event (best-effort, never raises).

        This is a fire-and-log operation: if publication fails, we log
        the error but do not change the caller's return value.
        """
        try:
            event = LoginAttemptFailed(
                aggregate_id=user_id or "unknown",
                failure_reason=failure_reason,
                ip_address=ip_address,
                user_agent=user_agent,
                user_id=user_id,
            )
            await self._event_publisher.publish([event])
        except Exception as e:
            logger.error(
                "Failed to publish LoginAttemptFailed event",
                extra={"failure_reason": failure_reason, "reason": str(e)},
            )

    async def _create_session(
        self,
        *,
        command: LoginUserCommand,
        user_id: UserId,
        email: Email,
        is_email_verified: bool,
        refresh_token_expires_at: datetime,
    ) -> _SessionResult:
        """
        Create a session, issue a refresh token, and sign an access token.

        Runs inside the Unit of Work. Any TravixError propagates to the UoW
        context and triggers a full rollback.

        Returns:
            (session, plain_refresh_token, access_token_str)

        Raises:
            TravixError subclass on expected failure — triggers UoW rollback.
            Exception on unexpected infrastructure failure.
        """
        session_id = SessionId(self._uuid.generate())

        # Issue refresh token (generates, hashes, persists record)
        refresh_result = await self._refresh_token_service.issue(
            session_id=session_id,
            user_id=user_id,
            expires_at=refresh_token_expires_at,
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
            expires_at=refresh_token_expires_at,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._session_repo.save(session)

        # Sign the access token (PyJWT is synchronous + CPU-bound, but fast enough
        # to run in the event loop — no asyncio.to_thread needed here)
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
            verified=is_email_verified,
        )
        access_token = self._jwt_service.create_access_token(claims)

        return session, plain_token, access_token


def _email_domain(raw_email: str) -> str:
    """Extract only the domain part of an email for safe structured log output."""
    parts = raw_email.split("@", 1)
    return parts[1] if len(parts) == 2 else "<unknown>"  # noqa: PLR2004
