"""
AuthenticationCredential aggregate root.

Owns the canonical email + password-hash pair for a user, tracks account
status, and records login activity. It is the aggregate root for the
"credential" sub-aggregate within the Authentication bounded context.

Invariants enforced by this aggregate:
  - Email is always normalised (lowercase, stripped) — enforced by Email VO.
  - Password hash is algorithm-agnostic and non-empty — enforced by PasswordHash VO.
  - A locked account cannot record a successful login without first having
    the lock cleared by record_successful_login().
  - A deactivated account cannot change its password.
  - password_changed_at is updated whenever the hash changes, enabling
    PasswordExpiryPolicy and ExpiredPasswordSpecification to work correctly.

Future extensibility (TASK-2.2 decision):
  This aggregate is intentionally password-specific. OAuth credentials,
  passkeys, and magic-link identities will be modelled as separate aggregate
  types (OAuthCredential, PasskeyCredential) rather than by adding nullable
  fields to this class. A CredentialRouter in the application layer selects
  the right aggregate type for each authentication flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.shared.domain.aggregate import AggregateRoot
from app.shared.domain.result import Failure, Result, Success
from app.modules.identity.authentication.domain.errors import AccountDisabledError
from app.modules.identity.authentication.domain.events.authentication_events import (
    PasswordChanged,
    UserRegistered,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


@dataclass(kw_only=True, eq=False)
class AuthenticationCredential(AggregateRoot[UserId]):
    """
    Aggregate root for a user's password-based authentication credentials.

    entity_id is the UserId — the same identity used across all contexts
    to identify this user.

    Password verification (bcrypt.checkpw or Argon2.verify) is NOT done
    here — it is done in the infrastructure layer's PasswordHasher adapter.
    The domain only stores and replaces the hash; it never sees plaintext.
    """

    email: Email
    password_hash: PasswordHash
    is_email_verified: bool = False
    is_active: bool = True
    failed_login_count: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        email: Email,
        password_hash: PasswordHash,
    ) -> "AuthenticationCredential":
        """
        Create a new credential and emit UserRegistered.

        The caller is responsible for:
          - Verifying the email is not already taken (EmailAlreadyExistsError).
          - Ensuring the password satisfies all policies before hashing.
        """
        now = datetime.now(UTC)
        credential = cls(
            entity_id=user_id,
            email=email,
            password_hash=password_hash,
            password_changed_at=now,
        )
        credential.push_event(
            UserRegistered(
                aggregate_id=str(user_id),
                user_id=str(user_id),
                email=str(email),
            )
        )
        return credential

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def user_id(self) -> UserId:
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_locked(self) -> bool:
        """True if the account lockout period has not yet elapsed."""
        if self.locked_until is None:
            return False
        return datetime.now(UTC) < self.locked_until

    # ------------------------------------------------------------------ #
    # Mutations                                                            #
    # ------------------------------------------------------------------ #

    def change_password(self, new_hash: PasswordHash) -> Result[None]:
        """
        Replace the password hash and emit PasswordChanged.

        Sets password_changed_at to now so PasswordExpiryPolicy and
        ExpiredPasswordSpecification have an accurate baseline.

        Returns Failure(AccountDisabledError) if the account is inactive.
        Callers should also revoke all other active sessions after a
        password change — this is an application-layer concern, not
        enforced here.
        """
        if not self.is_active:
            return Failure(AccountDisabledError())
        self.password_hash = new_hash
        self.password_changed_at = datetime.now(UTC)
        self.touch()
        self.push_event(
            PasswordChanged(
                aggregate_id=str(self.user_id),
                user_id=str(self.user_id),
            )
        )
        return Success(None)

    def record_successful_login(self) -> None:
        """
        Reset the failed-login counter and record the login timestamp.

        Call this AFTER verifying the password hash in the infrastructure
        layer. Clears any active lockout.
        """
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login_at = datetime.now(UTC)
        self.touch()

    def record_failed_login(
        self,
        *,
        max_attempts: int,
        lockout_duration: timedelta,
    ) -> None:
        """
        Increment the failed-login counter and apply a lockout if the
        threshold is reached.

        The caller decides max_attempts and lockout_duration via the
        AuthenticationPolicy — the domain records the outcome.
        """
        self.failed_login_count += 1
        if self.failed_login_count >= max_attempts:
            self.locked_until = datetime.now(UTC) + lockout_duration
        self.touch()

    def verify_email(self) -> None:
        """Mark the email address as verified."""
        self.is_email_verified = True
        self.touch()

    def deactivate(self) -> None:
        """
        Deactivate the account, preventing future logins.

        Does not automatically revoke active sessions — the application
        layer must do that separately via SessionRepository.
        """
        self.is_active = False
        self.touch()
