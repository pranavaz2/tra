"""
Authentication Application DTOs.

Data Transfer Objects returned by application use cases. These are
application-layer types — they are NOT Pydantic schemas and are NOT
directly serialised into HTTP responses. The API layer (router/schemas)
converts them into Pydantic response models before returning to the client.

Security invariant:
  RegistrationSummary and AuthenticatedSessionSummary carry sensitive values
  (access_token, plain_refresh_token). These fields use repr=False so they are
  excluded from dataclass-generated __repr__. The explicit __repr__ override
  provides a safe, log-friendly representation.

  NEVER log these summaries as a dict or via vars(). Always let the repr do
  the safe redaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from typing import TypeAlias

from app.shared.domain.result import Result
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class RegistrationSummary:
    """
    Summary of a completed registration operation.

    Returned by RegistrationService.execute() on success. The API layer
    reads these fields to build the HTTP 201 response.

    Fields:
        user_id:                   The newly created user's identity.
        email:                     Normalised email (from Email VO).
        is_email_verified:         True if verification was skipped or auto-applied.
        session_created:           True if create_session=True and succeeded.
        requires_email_verification: True if the user must still verify their email
                                    before performing authenticated operations.
        session_id:                Session ID if a session was created.
        access_token:              Signed JWT access token (repr=False — never logged).
        plain_refresh_token:       Opaque refresh token for rotation (repr=False).
                                   PlainRefreshToken.__repr__ itself returns [REDACTED],
                                   providing a second layer of protection.
    """

    user_id: UserId
    email: Email
    is_email_verified: bool
    session_created: bool
    requires_email_verification: bool
    session_id: SessionId | None = None
    access_token: str | None = field(default=None, repr=False)
    plain_refresh_token: PlainRefreshToken | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            f"RegistrationSummary("
            f"user_id={self.user_id!r}, "
            f"email={self.email}, "
            f"is_email_verified={self.is_email_verified}, "
            f"session_created={self.session_created}, "
            f"requires_email_verification={self.requires_email_verification}, "
            f"session_id={self.session_id!r}, "
            f"access_token=[REDACTED if set], "
            f"plain_refresh_token=[REDACTED if set])"
        )

    def __str__(self) -> str:
        return repr(self)


RegistrationResult: TypeAlias = "Result[RegistrationSummary]"


@dataclass(frozen=True)
class AuthenticatedSessionSummary:
    """
    Summary of a completed login operation.

    Returned by LoginService.execute() on success. The API layer reads these
    fields to build the HTTP 200 login response.

    Fields:
        user_id:                   The authenticated user's identity.
        email:                     Normalised email (from Email VO).
        session_id:                The newly created session's identity.
        access_token:              Signed JWT access token (repr=False — never logged).
        plain_refresh_token:       Opaque refresh token for rotation (repr=False).
                                   PlainRefreshToken.__repr__ returns [REDACTED].
        access_token_expires_at:   UTC datetime when the access token expires (15 min).
        refresh_token_expires_at:  UTC datetime when the refresh token expires (7 days).
        is_email_verified:         True if the user's email has been verified.
    """

    user_id: UserId
    email: Email
    session_id: SessionId
    access_token: str = field(repr=False)
    plain_refresh_token: PlainRefreshToken = field(repr=False)
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    is_email_verified: bool

    def __repr__(self) -> str:
        return (
            f"AuthenticatedSessionSummary("
            f"user_id={self.user_id!r}, "
            f"email={self.email}, "
            f"session_id={self.session_id!r}, "
            f"access_token=[REDACTED], "
            f"plain_refresh_token=[REDACTED], "
            f"access_token_expires_at={self.access_token_expires_at.isoformat()}, "
            f"refresh_token_expires_at={self.refresh_token_expires_at.isoformat()}, "
            f"is_email_verified={self.is_email_verified})"
        )

    def __str__(self) -> str:
        return repr(self)


LoginResult: TypeAlias = "Result[AuthenticatedSessionSummary]"
