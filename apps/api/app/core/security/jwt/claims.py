"""
Strongly typed JWT access token claims.

AccessTokenClaims:   All payload fields for a Travix access token.
DecodedAccessToken:  Full decoded token including JWT header metadata.
TokenType:           Discriminator enum for token type validation.

Design decisions:
  - Frozen dataclasses (not Pydantic models): zero I/O, pure value types.
  - datetime fields are always UTC-aware; callers must pass tz-aware datetimes.
  - `raw_token` uses field(repr=False) so the JWT string never appears in logs.
  - `type` defaults to "access"; token_version and session_version default to 1.
    Callers may override for explicit control. The service validates after decode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TokenType(str, Enum):
    """Discriminator for JWT token type claim."""

    ACCESS = "access"
    # Future: REFRESH = "refresh"  (only if refresh tokens become JWTs)


@dataclass(frozen=True)
class AccessTokenClaims:
    """
    Payload for a Travix AI access token.

    All standard JWT claims plus Travix-specific extensions.
    The caller is responsible for setting iat, exp, nbf, jti before encoding.
    Use ApplicationContext.clock for iat/nbf and compute exp from jwt_access_token_expire_minutes.

    Security notes:
      - `jti` must be a UUID v4; stored in Redis revocation list on logout.
      - `token_version` enables mass-invalidation of all user tokens (no Redis needed).
      - `session_version` enables per-session invalidation without waiting for exp.
      - `type` validated after every decode to prevent cross-type token confusion.
    """

    # -------------------------------------------------------------------------
    # RFC 7519 standard claims — all required
    # -------------------------------------------------------------------------
    sub: str           # Subject: User ID (UUID string)
    jti: str           # JWT ID (UUID string) — per-token revocation key
    iat: datetime      # Issued at (UTC-aware)
    exp: datetime      # Expires at (UTC-aware)
    nbf: datetime      # Not before (UTC-aware)
    iss: str           # Issuer (e.g. "https://api.travix.ai")
    aud: str           # Audience (e.g. "travix-mobile")

    # -------------------------------------------------------------------------
    # Travix custom claims — all required
    # -------------------------------------------------------------------------
    sid: str           # Session ID (UUID string)
    email: str         # User's email address at token issuance
    verified: bool     # Whether the user's email was verified at issuance

    # -------------------------------------------------------------------------
    # Claims with defaults — always present, rarely overridden
    # -------------------------------------------------------------------------
    type: str = TokenType.ACCESS.value              # Token type discriminator
    token_version: int = 1                          # Increment to invalidate all user tokens
    session_version: int = 1                        # Increment to invalidate this session only
    authentication_method: str = "password"         # AuthenticationMethod string value

    # -------------------------------------------------------------------------
    # Convenience aliases
    # -------------------------------------------------------------------------

    @property
    def user_id(self) -> str:
        """Alias for sub (User ID)."""
        return self.sub

    @property
    def session_id(self) -> str:
        """Alias for sid (Session ID)."""
        return self.sid

    @property
    def is_access_token(self) -> bool:
        """True if this is an access token (type == "access")."""
        return self.type == TokenType.ACCESS.value


@dataclass(frozen=True)
class DecodedAccessToken:
    """
    A fully decoded and verified access token.

    Returned by JWTService.verify_access_token() and decode_access_token().

    Attributes:
        claims:     Strongly typed payload from the JWT body.
        kid:        Key identifier from the JWT header.
        algorithm:  Signing algorithm from the JWT header.
        raw_token:  The original JWT string (excluded from repr/logs).
                    Used by logout flows to extract the JTI for revocation.
    """

    claims: AccessTokenClaims
    kid: str
    algorithm: str
    raw_token: str = field(repr=False)  # Never include in repr or log output
