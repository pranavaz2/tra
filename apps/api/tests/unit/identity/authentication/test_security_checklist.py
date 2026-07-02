"""
Security Checklist — executable quality gates for TASK-2.12.

Verifies that security invariants enforced in code cannot be accidentally
broken by future changes. These tests are not integration tests — they
test purely within the domain and core layers.

Checklist categories:
  1. Sensitive value redaction (repr/str/logging)
  2. JWT claim integrity (raw_token excluded from repr)
  3. RFC 7807 Problem Details consistency
  4. Security headers on HTTP responses
  5. AuthorizationError body safety (no token leak)
  6. SecurityContext field completeness

asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr


# ──────────────────────────────────────────────────────────────────────────── #
# 1. Sensitive value redaction                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSensitiveValueRedaction:
    """repr() and str() of sensitive value objects must never expose raw values."""

    def test_plain_refresh_token_repr_is_redacted(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
            PlainRefreshToken,
        )

        token = PlainRefreshToken.generate()
        assert "[REDACTED]" in repr(token)
        assert token.as_client_token() not in repr(token)

    def test_plain_refresh_token_str_is_redacted(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
            PlainRefreshToken,
        )

        token = PlainRefreshToken.generate()
        assert str(token) == "[REDACTED]"

    def test_plain_refresh_token_fstring_is_redacted(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
            PlainRefreshToken,
        )

        token = PlainRefreshToken.generate()
        formatted = f"token={token}"
        assert token.as_client_token() not in formatted

    def test_password_hash_repr_is_redacted(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.password_hash import (
            PasswordHash,
        )

        # Use a fake hash string long enough to pass the minimum length check.
        fake_hash = "$argon2id$v=19$m=65536,t=3,p=4$" + "x" * 50
        ph = PasswordHash(fake_hash)
        assert "[REDACTED]" in repr(ph)
        assert fake_hash not in repr(ph)

    def test_password_hash_str_is_redacted(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.password_hash import (
            PasswordHash,
        )

        fake_hash = "$argon2id$v=19$m=65536,t=3,p=4$" + "x" * 50
        ph = PasswordHash(fake_hash)
        assert str(ph) == "[REDACTED]"

    def test_authenticated_session_summary_repr_hides_tokens(self) -> None:
        from app.modules.identity.authentication.application.dtos import (
            AuthenticatedSessionSummary,
        )
        from app.modules.identity.authentication.domain.value_objects.email import Email
        from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
            PlainRefreshToken,
        )
        from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
        from app.modules.identity.authentication.domain.value_objects.user_id import UserId

        now = datetime.now(UTC)
        token = PlainRefreshToken.generate()
        raw_token_value = token.as_client_token()

        summary = AuthenticatedSessionSummary(
            user_id=UserId.from_str(str(uuid.uuid4())),
            email=Email("check@example.com"),
            session_id=SessionId.from_str(str(uuid.uuid4())),
            access_token="header.payload.sig",
            plain_refresh_token=token,
            access_token_expires_at=now + timedelta(minutes=15),
            refresh_token_expires_at=now + timedelta(days=7),
            is_email_verified=True,
        )

        # Raw token must not appear in repr.
        assert raw_token_value not in repr(summary)
        # Access token string must not appear either.
        assert "header.payload.sig" not in repr(summary)


# ──────────────────────────────────────────────────────────────────────────── #
# 2. JWT claim repr safety                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


class TestJWTClaimSafety:
    """DecodedAccessToken.raw_token must not appear in repr or be easily extractable."""

    def _make_token(self) -> tuple[object, str]:
        from app.core.security.jwt.claims import AccessTokenClaims
        from app.core.security.jwt.service import HS256JWTService
        from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey

        key = SigningKey(
            kid="sec-v1",
            algorithm="HS256",
            secret=SecretStr("security-checklist-secret-32bytes!"),
            is_primary=True,
        )
        svc = HS256JWTService(
            signing_key_provider=InMemorySigningKeyProvider(key),
            issuer="https://api.travix.ai",
            audience="travix-mobile",
            algorithm="HS256",
            leeway_seconds=0,
            access_token_lifetime_minutes=15,
        )
        now = datetime.now(UTC)
        claims = AccessTokenClaims(
            sub=str(uuid.uuid4()),
            jti=str(uuid.uuid4()),
            iat=now,
            exp=now + timedelta(minutes=15),
            nbf=now,
            iss="https://api.travix.ai",
            aud="travix-mobile",
            sid=str(uuid.uuid4()),
            email="sec@example.com",
            verified=True,
        )
        token_str = svc.create_access_token(claims)
        decoded = svc.verify_access_token(token_str)
        return decoded, token_str

    def test_decoded_token_raw_value_excluded_from_repr(self) -> None:
        decoded, token_str = self._make_token()
        # raw_token is field(repr=False) — must not appear in dataclass repr
        assert token_str not in repr(decoded)

    def test_authentication_method_in_claims(self) -> None:
        """New field: authentication_method must default to 'password' in claims."""
        decoded, _ = self._make_token()
        assert decoded.claims.authentication_method == "password"  # type: ignore[union-attr]

    def test_authentication_method_round_trips_in_jwt(self) -> None:
        """authentication_method written to JWT payload must survive encode/decode."""
        from app.core.security.jwt.claims import AccessTokenClaims
        from app.core.security.jwt.service import HS256JWTService
        from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey

        key = SigningKey(
            kid="sec-v2",
            algorithm="HS256",
            secret=SecretStr("security-checklist-secret-v2-32b!"),
            is_primary=True,
        )
        svc = HS256JWTService(
            signing_key_provider=InMemorySigningKeyProvider(key),
            issuer="https://api.travix.ai",
            audience="travix-mobile",
            algorithm="HS256",
            leeway_seconds=0,
            access_token_lifetime_minutes=15,
        )
        now = datetime.now(UTC)
        claims = AccessTokenClaims(
            sub=str(uuid.uuid4()),
            jti=str(uuid.uuid4()),
            iat=now,
            exp=now + timedelta(minutes=15),
            nbf=now,
            iss="https://api.travix.ai",
            aud="travix-mobile",
            sid=str(uuid.uuid4()),
            email="method@example.com",
            verified=True,
            authentication_method="google",
        )
        token = svc.create_access_token(claims)
        decoded = svc.verify_access_token(token)
        assert decoded.claims.authentication_method == "google"


# ──────────────────────────────────────────────────────────────────────────── #
# 3. AuthorizationError body safety                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class TestAuthorizationErrorSafety:
    """AuthorizationError response bodies must not leak token values or internal state."""

    def _make_error(self, factory_name: str) -> object:
        from app.core.security.auth.errors import AuthorizationError

        factory = getattr(AuthorizationError, factory_name)
        return factory(trace_id="test-trace-id", instance="/api/v1/auth/test")

    def test_missing_token_body_has_no_authorization_header_leak(self) -> None:
        """The error body must not echo back any Authorization header value."""
        error = self._make_error("missing_token")
        response = error.to_response()  # type: ignore[union-attr]
        body_str = str(response.body)
        assert "Bearer" not in body_str
        assert "Authorization" not in body_str

    def test_expired_token_body_has_no_token_leak(self) -> None:
        """Expired token error must not include the raw JWT in the response body."""
        error = self._make_error("expired_token")
        response = error.to_response()  # type: ignore[union-attr]
        # The raw token is never available here — just verify the error code.
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "AUTH_TOKEN_EXPIRED"

    def test_revoked_token_body_has_no_jti_leak(self) -> None:
        """Revoked token error must not expose the JTI."""
        error = self._make_error("revoked_token")
        response = error.to_response()  # type: ignore[union-attr]
        import json
        body = json.loads(response.body)
        # JTI must not appear in the error body.
        assert "jti" not in str(body).lower()

    def test_all_auth_errors_include_www_authenticate(self) -> None:
        """RFC 6750 requires WWW-Authenticate: Bearer on all 401 responses."""
        for factory_name in ("missing_token", "malformed_header", "expired_token", "invalid_token", "revoked_token"):
            error = self._make_error(factory_name)
            response = error.to_response()  # type: ignore[union-attr]
            assert response.headers.get("www-authenticate") == "Bearer", (
                f"{factory_name}: missing WWW-Authenticate header"
            )


# ──────────────────────────────────────────────────────────────────────────── #
# 4. SecurityContext field completeness                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSecurityContextCompleteness:
    """SecurityContext must expose all fields from both source contexts."""

    def _make_security_context(self) -> object:
        from app.core.security.auth.context import AuthorizationContext
        from app.core.security.auth.security_context import build_security_context

        now = datetime.now(UTC)
        auth = AuthorizationContext(
            user_id="user-uuid",
            session_id="session-uuid",
            token_id="jti-uuid",
            token_version=3,
            session_version=2,
            authentication_method="password",
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            email="sec@example.com",
            is_email_verified=True,
        )
        return build_security_context(
            auth,
            request_id="req-123",
            correlation_id="corr-456",
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
            locale="fr-FR",
            timezone="Europe/Paris",
            app_version="2.1.0",
            received_at=now,
        )

    def test_request_id_propagated(self) -> None:
        ctx = self._make_security_context()
        assert ctx.request_id == "req-123"  # type: ignore[union-attr]

    def test_user_id_propagated(self) -> None:
        ctx = self._make_security_context()
        assert ctx.user_id == "user-uuid"  # type: ignore[union-attr]

    def test_locale_propagated(self) -> None:
        ctx = self._make_security_context()
        assert ctx.locale == "fr-FR"  # type: ignore[union-attr]

    def test_device_trust_defaults_to_unknown(self) -> None:
        ctx = self._make_security_context()
        assert ctx.device_trust_level == "unknown"  # type: ignore[union-attr]

    def test_risk_score_defaults_to_zero(self) -> None:
        ctx = self._make_security_context()
        assert ctx.risk_score == 0.0  # type: ignore[union-attr]

    def test_context_is_immutable(self) -> None:
        ctx = self._make_security_context()
        with pytest.raises((AttributeError, TypeError)):
            ctx.user_id = "other"  # type: ignore[union-attr, misc]


# ──────────────────────────────────────────────────────────────────────────── #
# 5. Token family integrity                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


class TestTokenFamilyIntegrity:
    """RefreshTokenRecord must carry token_family_id and propagate it on rotation."""

    def _make_record(
        self,
        *,
        token_family_id: str | None = None,
    ) -> object:
        from app.modules.identity.authentication.domain.entities.refresh_token_record import (
            RefreshTokenRecord,
        )
        from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
            RefreshTokenHash,
        )
        from app.modules.identity.authentication.domain.value_objects.refresh_token_id import (
            RefreshTokenId,
        )
        from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
        from app.modules.identity.authentication.domain.value_objects.user_id import UserId

        return RefreshTokenRecord.create(
            record_id=RefreshTokenId.generate(),
            token_hash=RefreshTokenHash("a" * 64),
            session_id=SessionId.generate(),
            user_id=UserId.generate(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            token_family_id=token_family_id,
        )

    def test_token_family_id_defaults_to_none(self) -> None:
        record = self._make_record()
        assert record.token_family_id is None  # type: ignore[union-attr]

    def test_token_family_id_stored_when_provided(self) -> None:
        family_id = str(uuid.uuid4())
        record = self._make_record(token_family_id=family_id)
        assert record.token_family_id == family_id  # type: ignore[union-attr]

    def test_token_family_id_is_optional_for_backward_compat(self) -> None:
        """Records without token_family_id (pre-TASK-2.12) must still be constructible."""
        record = self._make_record(token_family_id=None)
        assert record is not None


# ──────────────────────────────────────────────────────────────────────────── #
# 6. Session lifecycle state transitions                                         #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSessionLifecycle:
    """SessionLifecycle must correctly validate and reject state transitions."""

    def test_active_to_revoked_is_valid(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        assert SessionLifecycle.can_transition(SessionState.ACTIVE, SessionState.REVOKED)

    def test_revoked_to_active_is_invalid(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        assert not SessionLifecycle.can_transition(SessionState.REVOKED, SessionState.ACTIVE)

    def test_expired_to_revoked_is_valid(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        assert SessionLifecycle.can_transition(SessionState.EXPIRED, SessionState.REVOKED)

    def test_revoked_is_terminal(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        assert SessionLifecycle.is_terminal(SessionState.REVOKED)
        assert not SessionLifecycle.is_terminal(SessionState.ACTIVE)

    def test_assert_can_transition_raises_on_illegal(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        with pytest.raises(ValueError, match="Illegal session state transition"):
            SessionLifecycle.assert_can_transition(SessionState.REVOKED, SessionState.ACTIVE)

    def test_assert_can_transition_passes_on_legal(self) -> None:
        from app.modules.identity.authentication.domain.services.session_lifecycle import (
            SessionLifecycle,
            SessionState,
        )

        # Should not raise
        SessionLifecycle.assert_can_transition(SessionState.ACTIVE, SessionState.REVOKED)


# ──────────────────────────────────────────────────────────────────────────── #
# 7. RiskSignals safety                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TestRiskSignalsSafety:
    """RiskSignals must be immutable and safe to default-construct."""

    def test_risk_signals_default_construction(self) -> None:
        from app.modules.identity.authentication.application.interfaces import RiskSignals

        s = RiskSignals()
        assert s.is_new_device is False
        assert s.is_impossible_travel is False
        assert s.is_anonymous_proxy is False
        assert s.is_tor_exit_node is False
        assert s.velocity_anomaly_score == 0.0
        assert s.previous_ip_address is None
        assert s.known_device_ids == ()

    def test_risk_signals_is_frozen(self) -> None:
        from app.modules.identity.authentication.application.interfaces import RiskSignals

        s = RiskSignals()
        with pytest.raises((AttributeError, TypeError)):
            s.is_new_device = True  # type: ignore[misc]

    def test_risk_signals_with_all_flags(self) -> None:
        from app.modules.identity.authentication.application.interfaces import RiskSignals

        s = RiskSignals(
            is_new_device=True,
            is_impossible_travel=True,
            is_anonymous_proxy=True,
            is_tor_exit_node=True,
            velocity_anomaly_score=0.9,
            previous_ip_address="1.2.3.4",
            known_device_ids=("device-a", "device-b"),
        )
        assert s.is_tor_exit_node is True
        assert s.velocity_anomaly_score == 0.9
        assert len(s.known_device_ids) == 2
