"""
HS256 JWT Service — concrete implementation of JWTService.

Security properties enforced by this implementation:

  Algorithm pinning:
    The `alg` header is checked BEFORE loading any key material. This prevents
    algorithm confusion attacks (e.g., an RS256 token submitted to an HS256
    server where the server might inadvertently use the public key as the HMAC
    secret). The configured algorithm is the only accepted algorithm.

  `kid` requirement:
    Every token header must contain a `kid` field. This enables zero-downtime
    key rotation: the old key remains available for verification (by kid lookup)
    while new tokens are signed with the new key.

  Constant-time verification:
    PyJWT delegates HMAC-SHA256 to the `cryptography` library (OpenSSL backend),
    which uses constant-time comparison via `CRYPTO_memcmp`. Signature verification
    is safe against timing side-channels.

  `type` claim validation:
    After decoding, the `type` claim is explicitly checked to equal "access".
    This prevents a future refresh-token-as-JWT from being accepted at an
    access-token-requiring endpoint.

  JTI for revocation:
    Every access token carries a `jti` (UUID). After logout, the JTI is stored
    in the Redis revocation blacklist (handled by TokenRevocationChecker — future).
    The JWT service does not perform revocation checks — it has no I/O capabilities.

  `token_version` and `session_version`:
    Present in the token payload for the auth middleware to validate against the
    stored credential and session records. The JWT service includes them as-is;
    the middleware validates them (future task).

  `verify_access_token` vs `decode_access_token`:
    - verify_access_token: validates everything including exp and nbf. Use in middleware.
    - decode_access_token: skips exp/nbf time checks; signature IS still verified.
      Use only in logout flows where the token may have just expired.

RS256 migration path (ADR-003):
    Implement RS256JWTService following the JWTService Protocol. Switch the
    factory in dependencies.py from HS256JWTService to RS256JWTService.
    No other code changes required.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    MissingRequiredClaimError,
    PyJWTError,
)

from app.core.security.jwt.claims import AccessTokenClaims, DecodedAccessToken, TokenType
from app.core.security.jwt.errors import (
    JWTAlgorithmError,
    JWTError,
    JWTExpiredError,
    JWTInvalidAudienceError,
    JWTInvalidIssuerError,
    JWTInvalidSignatureError,
    JWTMalformedError,
    JWTMissingClaimError,
    JWTNotYetValidError,
    JWTTokenTypeMismatchError,
)
from app.core.security.jwt.interfaces import SigningKeyProvider
from app.core.security.jwt.signing import SigningKey

_logger = logging.getLogger(__name__)

# Standard JWT claims that must be present and are verified by PyJWT.
_REQUIRED_STANDARD_CLAIMS: list[str] = ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]


class HS256JWTService:
    """
    JWT access token service using HMAC-SHA256.

    Accepts explicit parameters rather than a Settings object so that tests
    can construct it without environment variables. The dependencies.py factory
    wires Settings → HS256JWTService.
    """

    _ALGORITHM = "HS256"

    def __init__(
        self,
        *,
        signing_key_provider: SigningKeyProvider,
        issuer: str,
        audience: str,
        algorithm: str,
        leeway_seconds: int,
        access_token_lifetime_minutes: int,
    ) -> None:
        """
        Args:
            signing_key_provider:         Provides signing and verification keys.
            issuer:                       Expected 'iss' claim value.
            audience:                     Expected 'aud' claim value.
            algorithm:                    Must be "HS256".
            leeway_seconds:               Clock-skew tolerance for exp/nbf checks.
            access_token_lifetime_minutes: Informational only — callers set exp.

        Raises:
            ValueError: if algorithm is not "HS256".
        """
        if algorithm != self._ALGORITHM:
            raise ValueError(
                f"HS256JWTService requires algorithm 'HS256', got {algorithm!r}."
            )
        self._key_provider = signing_key_provider
        self._issuer = issuer
        self._audience = audience
        self._leeway = timedelta(seconds=leeway_seconds)
        self._token_lifetime = timedelta(minutes=access_token_lifetime_minutes)

    # -------------------------------------------------------------------------
    # Public interface (implements JWTService protocol)
    # -------------------------------------------------------------------------

    def create_access_token(self, claims: AccessTokenClaims) -> str:
        """Encode and sign an access token. See JWTService.create_access_token."""
        signing_key = self._key_provider.get_signing_key()
        payload = self._claims_to_payload(claims)
        try:
            token: str = jwt.encode(
                payload,
                signing_key.secret.get_secret_value(),
                algorithm=signing_key.algorithm,
                headers={"kid": signing_key.kid},
            )
        except Exception as exc:
            _logger.exception("Unexpected error encoding JWT.")
            raise JWTError("Token creation failed due to an internal error.") from exc
        return token

    def verify_access_token(self, token: str) -> DecodedAccessToken:
        """Fully validate an access token. See JWTService.verify_access_token."""
        return self._decode_token(token, verify_exp=True)

    def decode_access_token(self, token: str) -> DecodedAccessToken:
        """Signature-verified, expiry-tolerant decode. See JWTService.decode_access_token."""
        return self._decode_token(token, verify_exp=False)

    def validate_claims(self, claims: AccessTokenClaims) -> None:
        """Validate a claims object in memory. See JWTService.validate_claims."""
        if claims.type != TokenType.ACCESS.value:
            raise JWTTokenTypeMismatchError(
                f"Expected token type {TokenType.ACCESS.value!r}, got {claims.type!r}."
            )
        if claims.iss != self._issuer:
            raise JWTInvalidIssuerError(
                f"Claim 'iss' is {claims.iss!r}, expected {self._issuer!r}."
            )
        if claims.aud != self._audience:
            raise JWTInvalidAudienceError(
                f"Claim 'aud' is {claims.aud!r}, expected {self._audience!r}."
            )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _decode_token(self, token: str, *, verify_exp: bool) -> DecodedAccessToken:
        """Core decode path shared by verify_access_token and decode_access_token."""
        alg, kid, key = self._resolve_verification_key(token)
        payload = self._decode_with_key(token, key, verify_exp=verify_exp)
        claims = self._payload_to_claims(payload)
        self._validate_type_claim(claims)
        return DecodedAccessToken(
            claims=claims,
            kid=kid,
            algorithm=alg,
            raw_token=token,
        )

    def _resolve_verification_key(self, token: str) -> tuple[str, str, SigningKey]:
        """
        Parse the JWT header without verification and resolve the signing key.

        Validates that the `alg` header matches the configured algorithm and
        that a `kid` header is present. This check happens BEFORE any key
        material is loaded, preventing algorithm confusion attacks.

        Returns:
            (algorithm, kid, signing_key)

        Raises:
            JWTMalformedError:        header cannot be parsed, or kid is missing.
            JWTAlgorithmError:        alg header does not match configured algorithm.
            JWTInvalidSignatureError: no key found for the given kid.
        """
        try:
            header = jwt.get_unverified_header(token)
        except DecodeError as exc:
            raise JWTMalformedError("Token is not a valid JWT.") from exc

        alg: str = header.get("alg", "")
        kid: str = header.get("kid", "")

        if alg != self._ALGORITHM:
            raise JWTAlgorithmError(
                f"Token algorithm {alg!r} is not accepted. "
                f"Only {self._ALGORITHM!r} tokens are valid."
            )
        if not kid:
            raise JWTMalformedError(
                "JWT header is missing the 'kid' (key ID) field. "
                "All Travix access tokens must include a key identifier."
            )

        keys = self._key_provider.get_verification_keys(kid)
        if not keys:
            raise JWTInvalidSignatureError(
                f"No verification key found for kid={kid!r}. "
                "The signing key may have been rotated and the previous key removed."
            )

        return alg, kid, keys[0]

    def _decode_with_key(
        self,
        token: str,
        key: SigningKey,
        *,
        verify_exp: bool,
    ) -> dict[str, object]:
        """
        Call jwt.decode() and map all PyJWT exceptions to domain errors.

        When verify_exp=False (decode_access_token), exp and nbf time checks
        are skipped but the signature is still fully verified.
        """
        options: dict[str, object] = {
            "require": _REQUIRED_STANDARD_CLAIMS,
            "verify_exp": verify_exp,
            "verify_nbf": verify_exp,
        }
        try:
            payload: dict[str, object] = jwt.decode(
                token,
                key.secret.get_secret_value(),
                algorithms=[self._ALGORITHM],
                options=options,
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
            )
        except ExpiredSignatureError as exc:
            raise JWTExpiredError("Access token has expired.") from exc
        except ImmatureSignatureError as exc:
            raise JWTNotYetValidError(
                "Access token is not yet valid (nbf claim is in the future)."
            ) from exc
        except MissingRequiredClaimError as exc:
            raise JWTMissingClaimError(f"Required JWT claim is missing: {exc!s}") from exc
        except InvalidIssuerError as exc:
            raise JWTInvalidIssuerError("Token issuer is not trusted.") from exc
        except InvalidAudienceError as exc:
            raise JWTInvalidAudienceError("Token audience does not match.") from exc
        except InvalidSignatureError as exc:
            raise JWTInvalidSignatureError("Token signature verification failed.") from exc
        except DecodeError as exc:
            raise JWTMalformedError("Token structure is invalid.") from exc
        except PyJWTError as exc:
            raise JWTError("Token validation failed.") from exc
        return payload

    def _claims_to_payload(self, claims: AccessTokenClaims) -> dict[str, object]:
        """Serialize AccessTokenClaims to a JWT payload dict."""
        return {
            "sub": claims.sub,
            "jti": claims.jti,
            "iat": int(claims.iat.timestamp()),
            "exp": int(claims.exp.timestamp()),
            "nbf": int(claims.nbf.timestamp()),
            "iss": claims.iss,
            "aud": claims.aud,
            "sid": claims.sid,
            "email": claims.email,
            "verified": claims.verified,
            "type": claims.type,
            "token_version": claims.token_version,
            "session_version": claims.session_version,
            "authentication_method": claims.authentication_method,
        }

    def _payload_to_claims(self, payload: dict[str, object]) -> AccessTokenClaims:
        """Deserialize a decoded JWT payload dict to AccessTokenClaims."""
        try:
            aud_raw = payload["aud"]
            aud = aud_raw if isinstance(aud_raw, str) else str(list(aud_raw)[0])  # type: ignore[arg-type]
            return AccessTokenClaims(
                sub=str(payload["sub"]),
                jti=str(payload["jti"]),
                iat=datetime.fromtimestamp(float(str(payload["iat"])), UTC),
                exp=datetime.fromtimestamp(float(str(payload["exp"])), UTC),
                nbf=datetime.fromtimestamp(float(str(payload["nbf"])), UTC),
                iss=str(payload["iss"]),
                aud=aud,
                sid=str(payload["sid"]),
                email=str(payload["email"]),
                verified=bool(payload["verified"]),
                type=str(payload["type"]),
                token_version=int(str(payload["token_version"])),
                session_version=int(str(payload["session_version"])),
                # authentication_method: fall back to "password" for tokens issued before
                # this field was introduced (TASK-2.12 migration window).
                authentication_method=str(payload.get("authentication_method", "password")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise JWTMissingClaimError(
                f"Token payload is missing a required custom claim: {exc!s}"
            ) from exc

    def _validate_type_claim(self, claims: AccessTokenClaims) -> None:
        """Validate the token type claim to prevent cross-type token confusion."""
        if claims.type != TokenType.ACCESS.value:
            raise JWTTokenTypeMismatchError(
                f"Expected token type {TokenType.ACCESS.value!r}, got {claims.type!r}. "
                "Ensure you are submitting an access token, not a refresh token."
            )
