"""
Unit tests for HS256JWTService.

All tests are pure unit tests — no database, no Redis, no environment variables.
The service and key provider are constructed directly with test constants.

Coverage:
  - Token creation: structure, algorithm header, kid header, correct signing key
  - Full verification: valid tokens, all failure modes (expired, tampered, wrong issuer/aud,
    malformed, unsupported algorithm, missing kid, unknown kid, wrong type, future nbf)
  - Expiry-tolerant decode: expired tokens decode OK; invalid signatures still raise
  - Clock skew: leeway accepts tokens just-expired; rejects tokens well-expired
  - Custom claims round-trip: jti, token_version, session_version, aliases
  - Key rotation: old-key tokens verify when old key in provider; fail when removed
  - validate_claims: in-memory validation of type, issuer, audience
  - Security properties: raw_token excluded from repr; key secret excluded from repr
  - InMemorySigningKeyProvider: duplicate kid rejected; non-primary as first arg rejected
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest
from pydantic import SecretStr

from app.core.security.jwt.claims import AccessTokenClaims, DecodedAccessToken, TokenType
from app.core.security.jwt.errors import (
    JWTAlgorithmError,
    JWTExpiredError,
    JWTInvalidAudienceError,
    JWTInvalidIssuerError,
    JWTInvalidSignatureError,
    JWTMalformedError,
    JWTMissingClaimError,
    JWTNotYetValidError,
    JWTTokenTypeMismatchError,
)
from app.core.security.jwt.service import HS256JWTService
from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey

# ---------------------------------------------------------------------------
# Test constants — not real secrets, used only in this test module
# ---------------------------------------------------------------------------

_SECRET_V1 = "test-signing-secret-v1-must-be-at-least-32-chars"
_SECRET_V2 = "test-signing-secret-v2-must-be-at-least-32-chars"
_KID_V1 = "test-v1"
_KID_V2 = "test-v2"
_ISSUER = "https://api.travix.ai"
_AUDIENCE = "travix-mobile"


# ---------------------------------------------------------------------------
# Test infrastructure helpers
# ---------------------------------------------------------------------------


class _TestKeyProvider:
    """Minimal SigningKeyProvider for unit tests. Not for production use."""

    def __init__(self, *keys: SigningKey) -> None:
        self._by_kid: dict[str, SigningKey] = {k.kid: k for k in keys}
        self._primary = next(k for k in keys if k.is_primary)

    def get_signing_key(self) -> SigningKey:
        return self._primary

    def get_verification_keys(self, kid: str | None) -> list[SigningKey]:
        if kid is None:
            return list(self._by_kid.values())
        key = self._by_kid.get(kid)
        return [key] if key is not None else []


def _key(
    kid: str = _KID_V1,
    secret: str = _SECRET_V1,
    *,
    is_primary: bool = True,
) -> SigningKey:
    return SigningKey(kid=kid, algorithm="HS256", secret=SecretStr(secret), is_primary=is_primary)


def _service(
    provider: _TestKeyProvider | None = None,
    *,
    issuer: str = _ISSUER,
    audience: str = _AUDIENCE,
    leeway_seconds: int = 0,
    lifetime_minutes: int = 15,
) -> HS256JWTService:
    if provider is None:
        provider = _TestKeyProvider(_key())
    return HS256JWTService(
        signing_key_provider=provider,
        issuer=issuer,
        audience=audience,
        algorithm="HS256",
        leeway_seconds=leeway_seconds,
        access_token_lifetime_minutes=lifetime_minutes,
    )


def _claims(
    *,
    now: datetime | None = None,
    exp_offset_minutes: float = 15,
    nbf_offset_minutes: float = 0,
    issuer: str = _ISSUER,
    audience: str = _AUDIENCE,
    token_type: str = "access",
    token_version: int = 1,
    session_version: int = 1,
    sub: str | None = None,
    jti: str | None = None,
) -> AccessTokenClaims:
    _now = now or datetime.now(UTC)
    return AccessTokenClaims(
        sub=sub or str(uuid4()),
        jti=jti or str(uuid4()),
        iat=_now,
        exp=_now + timedelta(minutes=exp_offset_minutes),
        nbf=_now + timedelta(minutes=nbf_offset_minutes),
        iss=issuer,
        aud=audience,
        sid=str(uuid4()),
        email="test@example.com",
        verified=True,
        type=token_type,
        token_version=token_version,
        session_version=session_version,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestTokenCreation:
    def test_returns_non_empty_string(self) -> None:
        token = _service().create_access_token(_claims())
        assert isinstance(token, str) and token

    def test_token_has_three_dot_separated_parts(self) -> None:
        token = _service().create_access_token(_claims())
        assert token.count(".") == 2

    def test_header_algorithm_is_hs256(self) -> None:
        token = _service().create_access_token(_claims())
        assert pyjwt.get_unverified_header(token)["alg"] == "HS256"

    def test_header_kid_matches_signing_key(self) -> None:
        token = _service().create_access_token(_claims())
        assert pyjwt.get_unverified_header(token)["kid"] == _KID_V1

    def test_header_kid_reflects_primary_key_after_rotation(self) -> None:
        """After key rotation, new tokens carry the new primary key's kid."""
        provider = _TestKeyProvider(
            _key(kid=_KID_V2, secret=_SECRET_V2, is_primary=True),
            _key(kid=_KID_V1, secret=_SECRET_V1, is_primary=False),
        )
        token = _service(provider).create_access_token(_claims())
        assert pyjwt.get_unverified_header(token)["kid"] == _KID_V2


class TestTokenVerification:
    def test_valid_token_returns_decoded_token(self) -> None:
        svc = _service()
        c = _claims()
        decoded = svc.verify_access_token(svc.create_access_token(c))
        assert isinstance(decoded, DecodedAccessToken)
        assert decoded.claims.sub == c.sub

    def test_all_standard_claims_are_preserved(self) -> None:
        svc = _service()
        c = _claims()
        decoded = svc.verify_access_token(svc.create_access_token(c))
        dc = decoded.claims
        assert dc.sub == c.sub
        assert dc.jti == c.jti
        assert dc.sid == c.sid
        assert dc.email == c.email
        assert dc.verified == c.verified
        assert dc.iss == c.iss
        assert dc.aud == c.aud
        assert dc.type == c.type

    def test_decoded_token_has_correct_kid_and_algorithm(self) -> None:
        svc = _service()
        decoded = svc.verify_access_token(svc.create_access_token(_claims()))
        assert decoded.kid == _KID_V1
        assert decoded.algorithm == "HS256"

    def test_expired_token_raises_jwt_expired_error(self) -> None:
        svc = _service()
        token = svc.create_access_token(_claims(exp_offset_minutes=-1))
        with pytest.raises(JWTExpiredError):
            svc.verify_access_token(token)

    def test_tampered_signature_raises_invalid_signature_or_malformed(self) -> None:
        svc = _service()
        token = svc.create_access_token(_claims())
        # Replace last 10 chars of signature to corrupt HMAC
        tampered = token[:-10] + ("A" * 10)
        with pytest.raises((JWTInvalidSignatureError, JWTMalformedError)):
            svc.verify_access_token(tampered)

    def test_wrong_issuer_raises_invalid_issuer_error(self) -> None:
        svc = _service()
        token = svc.create_access_token(_claims(issuer="https://evil.example.com"))
        with pytest.raises(JWTInvalidIssuerError):
            svc.verify_access_token(token)

    def test_wrong_audience_raises_invalid_audience_error(self) -> None:
        svc = _service()
        token = svc.create_access_token(_claims(audience="wrong-client"))
        with pytest.raises(JWTInvalidAudienceError):
            svc.verify_access_token(token)

    def test_random_string_raises_malformed_error(self) -> None:
        svc = _service()
        with pytest.raises(JWTMalformedError):
            svc.verify_access_token("not-a-jwt-at-all")

    def test_three_part_garbage_raises_malformed_error(self) -> None:
        svc = _service()
        with pytest.raises(JWTMalformedError):
            svc.verify_access_token("aaa.bbb.ccc")

    def test_different_algorithm_in_header_raises_algorithm_error(self) -> None:
        """Token whose header says HS384 is rejected before any key lookup."""
        payload = {
            "sub": str(uuid4()), "jti": str(uuid4()),
            "iat": 0, "exp": 9_999_999_999, "nbf": 0,
            "iss": _ISSUER, "aud": _AUDIENCE,
            "sid": str(uuid4()), "email": "x@x.com", "verified": True,
            "type": "access", "token_version": 1, "session_version": 1,
        }
        wrong_alg_token = pyjwt.encode(
            payload, _SECRET_V1, algorithm="HS384", headers={"kid": _KID_V1}
        )
        with pytest.raises(JWTAlgorithmError):
            _service().verify_access_token(wrong_alg_token)

    def test_missing_kid_in_header_raises_malformed_error(self) -> None:
        """Tokens without a kid header are rejected (kid is required for rotation support)."""
        payload = {
            "sub": str(uuid4()), "jti": str(uuid4()),
            "iat": 0, "exp": 9_999_999_999, "nbf": 0,
            "iss": _ISSUER, "aud": _AUDIENCE,
            "sid": str(uuid4()), "email": "x@x.com", "verified": True,
            "type": "access", "token_version": 1, "session_version": 1,
        }
        no_kid_token = pyjwt.encode(payload, _SECRET_V1, algorithm="HS256")
        with pytest.raises(JWTMalformedError):
            _service().verify_access_token(no_kid_token)

    def test_unknown_kid_raises_invalid_signature_error(self) -> None:
        """Token with a kid that doesn't match any known key is rejected."""
        payload = {
            "sub": str(uuid4()), "jti": str(uuid4()),
            "iat": 0, "exp": 9_999_999_999, "nbf": 0,
            "iss": _ISSUER, "aud": _AUDIENCE,
            "sid": str(uuid4()), "email": "x@x.com", "verified": True,
            "type": "access", "token_version": 1, "session_version": 1,
        }
        unknown_kid_token = pyjwt.encode(
            payload, _SECRET_V1, algorithm="HS256", headers={"kid": "unknown-key"}
        )
        with pytest.raises(JWTInvalidSignatureError):
            _service().verify_access_token(unknown_kid_token)

    def test_wrong_token_type_raises_type_mismatch_error(self) -> None:
        """Type claim is validated even after successful signature verification."""
        svc = _service()
        token = svc.create_access_token(_claims(token_type="refresh"))
        with pytest.raises(JWTTokenTypeMismatchError):
            svc.verify_access_token(token)

    def test_nbf_in_future_raises_not_yet_valid_error(self) -> None:
        """Tokens where nbf is in the future are rejected."""
        svc = _service()
        token = svc.create_access_token(_claims(nbf_offset_minutes=5))
        with pytest.raises(JWTNotYetValidError):
            svc.verify_access_token(token)

    def test_missing_custom_claim_raises_missing_claim_error(self) -> None:
        """Tokens missing custom claims (e.g. sid) raise JWTMissingClaimError."""
        payload = {
            "sub": str(uuid4()), "jti": str(uuid4()),
            "iat": 0, "exp": 9_999_999_999, "nbf": 0,
            "iss": _ISSUER, "aud": _AUDIENCE,
            # Missing: sid, email, verified, type, token_version, session_version
        }
        token = pyjwt.encode(payload, _SECRET_V1, algorithm="HS256", headers={"kid": _KID_V1})
        with pytest.raises(JWTMissingClaimError):
            _service().verify_access_token(token)


class TestDecodeWithExpiredTolerance:
    def test_valid_token_succeeds(self) -> None:
        svc = _service()
        c = _claims()
        decoded = svc.decode_access_token(svc.create_access_token(c))
        assert decoded.claims.sub == c.sub

    def test_expired_token_returns_decoded_token(self) -> None:
        """decode_access_token tolerates expiry — use in logout flows."""
        svc = _service()
        expired_c = _claims(exp_offset_minutes=-5)
        token = svc.create_access_token(expired_c)
        decoded = svc.decode_access_token(token)
        assert decoded.claims.sub == expired_c.sub
        assert decoded.claims.jti == expired_c.jti
        assert decoded.claims.sid == expired_c.sid

    def test_tampered_signature_still_raises_even_when_tolerating_expiry(self) -> None:
        """Expiry tolerance does NOT bypass signature verification."""
        svc = _service()
        token = svc.create_access_token(_claims(exp_offset_minutes=-5))
        tampered = token[:-10] + ("B" * 10)
        with pytest.raises((JWTInvalidSignatureError, JWTMalformedError)):
            svc.decode_access_token(tampered)

    def test_wrong_issuer_still_raises_when_tolerating_expiry(self) -> None:
        """Issuer validation is NOT relaxed in decode_access_token."""
        svc = _service()
        token = svc.create_access_token(
            _claims(exp_offset_minutes=-5, issuer="https://evil.example.com")
        )
        with pytest.raises(JWTInvalidIssuerError):
            svc.decode_access_token(token)


class TestClockSkew:
    def test_token_expired_within_leeway_passes(self) -> None:
        """Token expired 10 seconds ago passes when leeway=30s."""
        svc = _service(leeway_seconds=30)
        now = datetime.now(UTC)
        c = AccessTokenClaims(
            sub=str(uuid4()), jti=str(uuid4()),
            iat=now - timedelta(minutes=15, seconds=10),
            exp=now - timedelta(seconds=10),
            nbf=now - timedelta(minutes=15, seconds=10),
            iss=_ISSUER, aud=_AUDIENCE,
            sid=str(uuid4()), email="t@t.com", verified=True,
            type="access", token_version=1, session_version=1,
        )
        decoded = svc.verify_access_token(svc.create_access_token(c))
        assert decoded.claims.sub == c.sub

    def test_token_expired_beyond_leeway_fails(self) -> None:
        """Token expired 60 seconds ago fails when leeway=30s."""
        svc = _service(leeway_seconds=30)
        now = datetime.now(UTC)
        c = AccessTokenClaims(
            sub=str(uuid4()), jti=str(uuid4()),
            iat=now - timedelta(minutes=15, seconds=60),
            exp=now - timedelta(seconds=60),
            nbf=now - timedelta(minutes=15, seconds=60),
            iss=_ISSUER, aud=_AUDIENCE,
            sid=str(uuid4()), email="t@t.com", verified=True,
            type="access", token_version=1, session_version=1,
        )
        token = svc.create_access_token(c)
        with pytest.raises(JWTExpiredError):
            svc.verify_access_token(token)


class TestCustomClaims:
    def test_jti_round_trips(self) -> None:
        svc = _service()
        jti = str(uuid4())
        decoded = svc.verify_access_token(svc.create_access_token(_claims(jti=jti)))
        assert decoded.claims.jti == jti

    def test_token_version_round_trips(self) -> None:
        svc = _service()
        decoded = svc.verify_access_token(svc.create_access_token(_claims(token_version=7)))
        assert decoded.claims.token_version == 7

    def test_session_version_round_trips(self) -> None:
        svc = _service()
        decoded = svc.verify_access_token(svc.create_access_token(_claims(session_version=5)))
        assert decoded.claims.session_version == 5

    def test_user_id_alias_matches_sub(self) -> None:
        svc = _service()
        c = _claims()
        decoded = svc.verify_access_token(svc.create_access_token(c))
        assert decoded.claims.user_id == decoded.claims.sub

    def test_session_id_alias_matches_sid(self) -> None:
        svc = _service()
        c = _claims()
        decoded = svc.verify_access_token(svc.create_access_token(c))
        assert decoded.claims.session_id == decoded.claims.sid

    def test_is_access_token_returns_true(self) -> None:
        svc = _service()
        decoded = svc.verify_access_token(svc.create_access_token(_claims()))
        assert decoded.claims.is_access_token is True

    def test_timestamps_are_utc_aware(self) -> None:
        """Decoded datetime claims must be UTC-aware (not naive)."""
        svc = _service()
        decoded = svc.verify_access_token(svc.create_access_token(_claims()))
        assert decoded.claims.iat.tzinfo is not None
        assert decoded.claims.exp.tzinfo is not None
        assert decoded.claims.nbf.tzinfo is not None


class TestKeyRotation:
    def test_new_primary_key_signs_new_tokens(self) -> None:
        """After rotation, new tokens carry the new kid in the header."""
        provider = _TestKeyProvider(
            _key(kid=_KID_V2, secret=_SECRET_V2, is_primary=True),
            _key(kid=_KID_V1, secret=_SECRET_V1, is_primary=False),
        )
        token = _service(provider).create_access_token(_claims())
        assert pyjwt.get_unverified_header(token)["kid"] == _KID_V2

    def test_old_key_tokens_still_verify_when_old_key_in_provider(self) -> None:
        """Old tokens verify successfully as long as the old key is in the provider."""
        # v1 service signs with old key
        svc_v1 = _service(_TestKeyProvider(_key(kid=_KID_V1, secret=_SECRET_V1)))
        old_claims = _claims()
        old_token = svc_v1.create_access_token(old_claims)

        # v2 service: new primary key + old key for verification
        svc_v2 = _service(
            _TestKeyProvider(
                _key(kid=_KID_V2, secret=_SECRET_V2, is_primary=True),
                _key(kid=_KID_V1, secret=_SECRET_V1, is_primary=False),
            )
        )
        decoded = svc_v2.verify_access_token(old_token)
        assert decoded.claims.sub == old_claims.sub
        assert decoded.kid == _KID_V1

    def test_old_key_token_fails_after_old_key_removed(self) -> None:
        """Once the old key is removed from the provider, old tokens are rejected."""
        svc_v1 = _service(_TestKeyProvider(_key(kid=_KID_V1, secret=_SECRET_V1)))
        old_token = svc_v1.create_access_token(_claims())

        # v2 service with ONLY the new key — old key gone
        svc_v2 = _service(_TestKeyProvider(_key(kid=_KID_V2, secret=_SECRET_V2)))
        with pytest.raises(JWTInvalidSignatureError):
            svc_v2.verify_access_token(old_token)


class TestValidateClaims:
    def test_valid_claims_pass_without_error(self) -> None:
        _service().validate_claims(_claims())  # Must not raise

    def test_wrong_type_raises_token_type_mismatch(self) -> None:
        with pytest.raises(JWTTokenTypeMismatchError):
            _service().validate_claims(_claims(token_type="refresh"))

    def test_wrong_issuer_raises_invalid_issuer(self) -> None:
        with pytest.raises(JWTInvalidIssuerError):
            _service().validate_claims(_claims(issuer="https://wrong.example.com"))

    def test_wrong_audience_raises_invalid_audience(self) -> None:
        with pytest.raises(JWTInvalidAudienceError):
            _service().validate_claims(_claims(audience="wrong-client"))


class TestSecurityProperties:
    def test_raw_token_excluded_from_decoded_access_token_repr(self) -> None:
        """The JWT string must never appear in repr (it would appear in logs)."""
        svc = _service()
        token = svc.create_access_token(_claims())
        decoded = svc.verify_access_token(token)
        assert token not in repr(decoded)

    def test_signing_key_secret_excluded_from_repr(self) -> None:
        """SecretStr wrapping ensures the key material is never in repr."""
        k = _key()
        assert _SECRET_V1 not in repr(k)
        assert _SECRET_V1 not in str(k)

    def test_hs256_service_rejects_non_hs256_algorithm_at_construction(self) -> None:
        """HS256JWTService validates its algorithm parameter at construction time."""
        with pytest.raises(ValueError, match="HS256"):
            HS256JWTService(
                signing_key_provider=_TestKeyProvider(_key()),
                issuer=_ISSUER,
                audience=_AUDIENCE,
                algorithm="RS256",
                leeway_seconds=0,
                access_token_lifetime_minutes=15,
            )

    def test_token_type_enum_value_is_access(self) -> None:
        assert TokenType.ACCESS.value == "access"


class TestInMemorySigningKeyProvider:
    def test_duplicate_kid_raises_value_error(self) -> None:
        k1 = _key(kid="same", is_primary=True)
        k2 = _key(kid="same", secret=_SECRET_V2, is_primary=False)
        with pytest.raises(ValueError, match="Duplicate"):
            InMemorySigningKeyProvider(k1, k2)

    def test_non_primary_first_arg_raises_value_error(self) -> None:
        k = _key(is_primary=False)
        with pytest.raises(ValueError, match="is_primary"):
            InMemorySigningKeyProvider(k)

    def test_get_signing_key_returns_primary(self) -> None:
        primary = _key(kid=_KID_V1, is_primary=True)
        provider = InMemorySigningKeyProvider(primary)
        assert provider.get_signing_key() is primary

    def test_get_verification_keys_by_kid_returns_correct_key(self) -> None:
        primary = _key(kid=_KID_V1, is_primary=True)
        legacy = _key(kid=_KID_V2, secret=_SECRET_V2, is_primary=False)
        provider = InMemorySigningKeyProvider(primary, legacy)
        assert provider.get_verification_keys(_KID_V2) == [legacy]
        assert provider.get_verification_keys(_KID_V1) == [primary]

    def test_get_verification_keys_unknown_kid_returns_empty(self) -> None:
        provider = InMemorySigningKeyProvider(_key())
        assert provider.get_verification_keys("nonexistent-kid") == []

    def test_get_verification_keys_none_returns_all(self) -> None:
        primary = _key(kid=_KID_V1, is_primary=True)
        legacy = _key(kid=_KID_V2, secret=_SECRET_V2, is_primary=False)
        provider = InMemorySigningKeyProvider(primary, legacy)
        all_keys = provider.get_verification_keys(None)
        assert len(all_keys) == 2
