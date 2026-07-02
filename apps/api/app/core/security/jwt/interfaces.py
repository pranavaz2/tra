"""
JWT service interfaces — domain ports for the JWT infrastructure.

All authentication flows (login, OAuth, passkeys, registration auto-login) use
JWTService. Middleware validation uses JWTService. Nothing outside this package
should import from service.py or signing.py directly.

Future-ready placeholders:
  TokenRevocationChecker: Redis-backed JTI blacklist (TASK implementing logout).
  JWKSProvider:           Public key set for RS256 migration (ADR-003 §Migration).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.core.security.jwt.claims import AccessTokenClaims, DecodedAccessToken
from app.core.security.jwt.signing import SigningKey


@runtime_checkable
class JWTService(Protocol):
    """
    Port for JWT access token creation and validation.

    The application layer depends only on this Protocol; the concrete
    HS256JWTService (or future RS256JWTService) is injected via DI.
    PyJWT is never imported outside of app.core.security.jwt.

    Token lifecycle:
        create_access_token()   → encode + sign (login, registration, OAuth)
        verify_access_token()   → full validate (auth middleware, every request)
        decode_access_token()   → signature-verified, exp-tolerant (logout flows)
        validate_claims()       → in-memory claim check (pre-encode validation)
    """

    def create_access_token(self, claims: AccessTokenClaims) -> str:
        """
        Encode and sign an access token from the given claims.

        The caller sets all claims including iat, exp, nbf, and jti.
        Generate jti as uuid4(); compute iat/nbf from the clock; compute
        exp as iat + settings.jwt_access_token_expire_minutes.

        Returns:
            Compact JWT string (header.payload.signature).

        Raises:
            JWTError: if signing fails due to a key or encoding error.
        """
        ...

    def verify_access_token(self, token: str) -> DecodedAccessToken:
        """
        Fully validate an access token.

        Validates in order:
          1. JWT structure (parseable header and payload)
          2. Algorithm (must be the configured algorithm — algorithm confusion prevention)
          3. Key ID (kid must be present and known)
          4. Signature (HMAC constant-time comparison)
          5. Expiry (exp — with optional clock-skew leeway)
          6. Not-before (nbf)
          7. Issuer (iss)
          8. Audience (aud)
          9. Required custom claims (sid, email, verified, type, token_version, session_version)
          10. Token type (type == "access")

        Use in authentication middleware for every protected request.

        Raises:
            JWTExpiredError:           token has passed its exp claim.
            JWTNotYetValidError:       current time is before nbf.
            JWTInvalidSignatureError:  HMAC does not match.
            JWTMalformedError:         token string is not a valid JWT.
            JWTInvalidIssuerError:     iss does not match configured issuer.
            JWTInvalidAudienceError:   aud does not match configured audience.
            JWTTokenTypeMismatchError: type claim is not 'access'.
            JWTAlgorithmError:         alg header is not the configured algorithm.
            JWTMissingClaimError:      a required claim is absent.
        """
        ...

    def decode_access_token(self, token: str) -> DecodedAccessToken:
        """
        Decode and signature-verify a token, tolerating expiry.

        The JWT signature IS verified. Only exp and nbf time checks are skipped.
        Intended for logout flows where the client's access token may have just
        expired and the caller needs the jti or sid for revocation.

        DO NOT use in authentication middleware — use verify_access_token there.

        Raises:
            JWTInvalidSignatureError:  HMAC does not match (even when tolerating expiry).
            JWTMalformedError:         token string is not a valid JWT.
            JWTInvalidIssuerError:     iss does not match.
            JWTInvalidAudienceError:   aud does not match.
        """
        ...

    def validate_claims(self, claims: AccessTokenClaims) -> None:
        """
        Validate a claims object in memory without parsing a token string.

        Checks issuer, audience, and token type against the service configuration.
        Does NOT check time-sensitive claims (exp, nbf) — use verify_access_token
        for that.

        Intended for validating claims before calling create_access_token.

        Raises:
            JWTTokenTypeMismatchError: type is not 'access'.
            JWTInvalidIssuerError:     iss does not match configured issuer.
            JWTInvalidAudienceError:   aud does not match configured audience.
        """
        ...


@runtime_checkable
class SigningKeyProvider(Protocol):
    """
    Port for JWT signing key management.

    Abstracts key storage so JWTService never holds key material directly.
    The current implementation (InMemorySigningKeyProvider) reads from settings.
    Future implementations may read from AWS Secrets Manager or a KMS.

    Key rotation protocol (zero-downtime):
        1. Add new key with is_primary=True; old key remains in additional_keys.
        2. Deploy. New tokens use the new kid; old tokens verify via old kid.
        3. After ≤15 minutes (max access token lifetime), remove the old key.
    """

    def get_signing_key(self) -> SigningKey:
        """Return the current primary key for signing new tokens."""
        ...

    def get_verification_keys(self, kid: str | None) -> list[SigningKey]:
        """
        Return verification key(s) matching the given kid.

        If kid is None, return all available keys (fallback for tokens without kid).
        Returns empty list if no matching key is found (triggers JWTInvalidSignatureError).
        """
        ...


@runtime_checkable
class TokenRevocationChecker(Protocol):
    """
    Port for checking whether a specific access token has been revoked.

    PLACEHOLDER — to be implemented in the task that introduces logout.

    Design:
        - JWTService validates the token signature and claims (CPU-bound, no I/O).
        - TokenRevocationChecker checks the Redis JTI blacklist (I/O-bound, async).
        - Authentication middleware calls both in sequence.

    Redis key format:  revoked:jti:{jti}
    Redis DB:          redis_token_revocation_db (DB 2, requires AOF persistence —
                       losing this DB is a security vulnerability per CLAUDE.md §11)
    TTL:               token's remaining lifetime (claims.exp - now)

    Revocation events:
        - Logout (single session)
        - Logout-all (all sessions — each outstanding JTI is individually revoked)
        - Account deactivation
        - Stolen token detection (refresh token reuse)
    """

    async def is_revoked(self, jti: str) -> bool:
        """
        Return True if the JTI is in the revocation blacklist.

        This must complete in <10ms (Redis GET). Token validation depends on it
        for every authenticated request.
        """
        ...

    async def revoke(self, jti: str, expires_at: datetime) -> None:
        """
        Add a JTI to the revocation blacklist with TTL = expires_at - now.

        The TTL prevents unbounded Redis growth: once the token's natural expiry
        has passed, the revocation entry is no longer needed (expired tokens
        are already rejected by JWTService.verify_access_token).

        Call this during:
            - logout     → revoke the access token JTI
            - logout-all → revoke all outstanding access token JTIs for the user
        """
        ...


@runtime_checkable
class JWKSProvider(Protocol):
    """
    Port for the JSON Web Key Set (JWKS) endpoint.

    PLACEHOLDER — for the RS256 migration path described in ADR-003.

    When the backend migrates to RS256, this provider exposes the current
    public signing keys so downstream services can independently verify
    Travix access tokens without contacting the auth server.

    Endpoint: GET /api/v1/auth/.well-known/jwks.json

    JWKS key rotation:
        - Include both old and new public keys during the 15-minute grace period.
        - Clients discover the new key when they encounter an unknown kid.
        - Remove the old public key after the grace period.

    HS256 → RS256 migration timeline (ADR-003):
        Phase 1: Deploy JWKS endpoint (public keys only — HS256 secrets stay private).
        Phase 2: Issue RS256 tokens. Accept both HS256 and RS256 during rollover.
        Phase 3: Stop issuing HS256 tokens; deprecate HS256 verification.
    """

    def get_jwks(self) -> dict[str, object]:
        """
        Return the JSON Web Key Set (RFC 7517) for the current signing keys.

        Example (RS256):
            {
                "keys": [
                    {
                        "kty": "RSA", "use": "sig", "alg": "RS256",
                        "kid": "rs256-v1", "n": "<base64url>", "e": "AQAB"
                    }
                ]
            }
        """
        ...
