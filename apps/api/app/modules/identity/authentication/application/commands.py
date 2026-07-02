"""
Authentication Application Commands.

Strongly typed, immutable command objects for authentication use cases.
Commands cross the boundary between the API (presentation) layer and the
application layer. They carry raw, unvalidated user input — validation
(format checks) and domain enrichment (Email VO creation) happen inside
the application service.

Security invariant:
  RegisterUserCommand.password and LoginUserCommand.password MUST NOT appear
  in any log, repr, or str output. The field uses repr=False and __repr__ is
  overridden to enforce this. Any change that would expose plaintext passwords
  is a security regression.

Future OAuth / passkey commands:
  When OAuth and passkey flows are implemented, their commands will live here:
    OAuthRegisterCommand(provider, oauth_code, redirect_uri, ...)
    OAuthLoginCommand(provider, oauth_code, redirect_uri, ...)
    PasskeyRegisterCommand(passkey_credential_id, public_key, ...)
    PasskeyLoginCommand(passkey_credential_id, authenticator_data, ...)
  A LoginHandlerRouter dispatches based on the command type.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegisterUserCommand:
    """
    Command to register a new user with email and password credentials.

    Carries raw input from the API boundary. The application service is
    responsible for all validation and enrichment.

    Attributes:
        email:          Raw email string from the request body.
        password:       Plaintext password. NEVER logged. NEVER stored.
                        Hashed immediately after strength validation.
        device_id:      Client-reported device identifier (optional).
                        Stored on the session for audit purposes.
        device_name:    Human-readable device label (optional).
        platform:       Client platform — "ios", "android", "web" (optional).
        create_session: If True (default), the service creates an
                        AuthenticationSession and issues tokens after
                        credential creation (auto-login on registration).
                        Set to False for flows where the user must verify
                        their email before receiving tokens.
        ip_address:     Request IP address for audit logging (optional).
        user_agent:     HTTP User-Agent header for audit logging (optional).
    """

    email: str
    password: str = field(repr=False)
    device_id: str | None = None
    device_name: str | None = None
    platform: str | None = None
    create_session: bool = True
    ip_address: str | None = None
    user_agent: str | None = None

    def __repr__(self) -> str:
        return (
            f"RegisterUserCommand("
            f"email={self.email!r}, "
            f"password=[REDACTED], "
            f"device_id={self.device_id!r}, "
            f"platform={self.platform!r}, "
            f"create_session={self.create_session})"
        )

    def __str__(self) -> str:
        return repr(self)


@dataclass(frozen=True)
class LoginUserCommand:
    """
    Command to authenticate a user with email and password credentials.

    Carries raw input from the API boundary. The application service performs
    credential lookup, password verification, and token issuance.

    Attributes:
        email:       Raw email string from the request body.
        password:    Plaintext password. NEVER logged. NEVER stored.
                     Verified immediately against the stored hash and discarded.
        device_id:   Client-reported device identifier (optional). Stored on
                     the session for multi-device management and audit.
        device_name: Human-readable device label (optional).
        platform:    Client platform — "ios", "android", "web" (optional).
        ip_address:  Request IP address for risk assessment and audit logging.
        user_agent:  HTTP User-Agent header for audit logging.
    """

    email: str
    password: str = field(repr=False)
    device_id: str | None = None
    device_name: str | None = None
    platform: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    def __repr__(self) -> str:
        return (
            f"LoginUserCommand("
            f"email={self.email!r}, "
            f"password=[REDACTED], "
            f"device_id={self.device_id!r}, "
            f"platform={self.platform!r})"
        )

    def __str__(self) -> str:
        return repr(self)
