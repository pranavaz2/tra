"""
AuthorizationContext — immutable snapshot of a verified authentication state.

Created by get_authorization_context() after a token passes all validation
checks (structure → signature → expiry → issuer/audience → revocation).
Injected into route handlers via RequireAuthentication or OptionalAuthentication.

Design:
  - Frozen dataclass: no mutation after creation.
  - All IDs are plain strings (no domain value objects) — this is core infrastructure,
    not a feature module, and must not import from the identity domain.
  - authentication_method is a plain string discriminator to support future
    OAuth and passkey flows without changing the dataclass shape.
  - Extension point: add role/permission fields here when RBAC is introduced.
    The dependency chain (RequireAuthentication → get_authorization_context) will
    remain unchanged — only the field list and the factory function expand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuthorizationContext:
    """
    Verified identity state attached to a single authenticated request.

    Fields:
        user_id:               UUID string of the authenticated user (from JWT `sub`).
        session_id:            UUID string of the active session (from JWT `sid`).
        token_id:              UUID string of this specific token (JWT `jti`).
                               Used for per-token revocation (logout single device).
        token_version:         Monotonic counter. Increment server-side to invalidate
                               all tokens for this user without Redis.
        session_version:       Monotonic counter. Increment server-side to invalidate
                               this session only without Redis.
        authentication_method: How the user authenticated. Currently "password".
                               Future values: "oauth_google", "passkey", "sso".
        issued_at:             UTC datetime when the token was issued.
        expires_at:            UTC datetime when the token expires.
        email:                 Email address at token issuance time.
        is_email_verified:     Whether the email was verified at token issuance.
    """

    user_id: str
    session_id: str
    token_id: str
    token_version: int
    session_version: int
    authentication_method: str
    issued_at: datetime
    expires_at: datetime
    email: str
    is_email_verified: bool
