"""
JWT-specific error hierarchy.

All errors map to HTTP 401 Unauthorized (via the UnauthorizedError base class).
The exception handler in app.core.exceptions converts these to RFC 7807 responses
with the appropriate error_code from the authentication error catalogue.

Error catalogue mapping:
  JWTMalformedError          → AUTH_TOKEN_MALFORMED
  JWTExpiredError            → AUTH_TOKEN_EXPIRED
  JWTInvalidSignatureError   → AUTH_TOKEN_INVALID
  JWTInvalidIssuerError      → AUTH_TOKEN_INVALID
  JWTInvalidAudienceError    → AUTH_TOKEN_INVALID
  JWTNotYetValidError        → AUTH_TOKEN_INVALID
  JWTAlgorithmError          → AUTH_TOKEN_INVALID
  JWTTokenTypeMismatchError  → AUTH_TOKEN_INVALID
  JWTMissingClaimError       → AUTH_TOKEN_INVALID
  JWTRevokedError            → AUTH_TOKEN_REVOKED  (raised by TokenRevocationChecker)
  JWTError (base)            → AUTH_TOKEN_INVALID
"""

from __future__ import annotations

from app.shared.domain.errors import UnauthorizedError


class JWTError(UnauthorizedError):
    """
    Base class for all JWT validation failures.

    Catching JWTError catches every JWT-related failure. For precision,
    catch a specific subclass (JWTExpiredError, JWTInvalidSignatureError, etc.).
    Maps to HTTP 401 Unauthorized.
    """

    code = "auth_token_invalid"

    def __init__(self, message: str = "Token validation failed.") -> None:
        super().__init__(message)


class JWTExpiredError(JWTError):
    """Access token has passed its expiry time (exp claim)."""

    code = "auth_token_expired"

    def __init__(self, message: str = "Access token has expired.") -> None:
        super().__init__(message)


class JWTMalformedError(JWTError):
    """Token string is not a valid JWT structure (cannot be parsed)."""

    code = "auth_token_malformed"

    def __init__(self, message: str = "Token is malformed and cannot be parsed.") -> None:
        super().__init__(message)


class JWTInvalidSignatureError(JWTError):
    """HMAC signature verification failed — token was tampered with or signed by a different key."""

    code = "auth_token_invalid"

    def __init__(self, message: str = "Token signature is invalid.") -> None:
        super().__init__(message)


class JWTInvalidClaimError(JWTError):
    """A JWT claim failed validation (wrong value, invalid format, or missing)."""

    code = "auth_token_invalid"

    def __init__(self, message: str = "A required token claim is invalid.") -> None:
        super().__init__(message)


class JWTInvalidIssuerError(JWTInvalidClaimError):
    """The 'iss' claim does not match the configured trusted issuer."""

    def __init__(self, message: str = "Token issuer is not trusted.") -> None:
        super().__init__(message)


class JWTInvalidAudienceError(JWTInvalidClaimError):
    """The 'aud' claim does not match the configured expected audience."""

    def __init__(self, message: str = "Token audience does not match.") -> None:
        super().__init__(message)


class JWTNotYetValidError(JWTError):
    """Current time is before the token's 'nbf' (not before) claim."""

    code = "auth_token_invalid"

    def __init__(self, message: str = "Access token is not yet valid.") -> None:
        super().__init__(message)


class JWTAlgorithmError(JWTError):
    """Token uses an unsupported or unexpected signing algorithm."""

    code = "auth_token_invalid"

    def __init__(self, message: str = "Token uses an unsupported algorithm.") -> None:
        super().__init__(message)


class JWTTokenTypeMismatchError(JWTInvalidClaimError):
    """
    Token 'type' claim does not match the expected type ('access').

    Raised to prevent cross-type token confusion attacks — e.g., a client
    submitting a (hypothetical future) refresh-JWT where an access token is required.
    """

    def __init__(self, message: str = "Token type does not match the required type.") -> None:
        super().__init__(message)


class JWTMissingClaimError(JWTInvalidClaimError):
    """A required standard or custom claim is absent from the token payload."""

    def __init__(self, message: str = "A required token claim is missing.") -> None:
        super().__init__(message)


class JWTRevokedError(JWTError):
    """
    The token has been explicitly revoked.

    NOT raised by JWTService — it has no I/O capabilities.
    Raised by TokenRevocationChecker after finding the JTI in the Redis
    revocation blacklist. See interfaces.py for the full revocation flow.
    """

    code = "auth_token_revoked"

    def __init__(self, message: str = "This token has been revoked.") -> None:
        super().__init__(message)
