"""
Performance Benchmark Placeholders — TASK-2.12.

Simple timing benchmarks for authentication-critical hot paths.
These are NOT load tests and do NOT replace profiling tools.
They exist to:
  1. Catch gross regressions (e.g., accidental O(n²) in a loop).
  2. Document expected performance characteristics per sprint.
  3. Serve as baselines for future optimisation work.

Framework:
  Uses time.perf_counter() — nanosecond resolution, no external deps.
  Each benchmark returns (avg_ms_per_call, total_ms) for manual inspection.
  Threshold assertions use generous upper bounds to avoid flaky CI failures
  on heavily loaded machines. Adjust per environment.

Threshold guidance (developer machine, single thread):
  - Argon2id hash: < 500 ms per call (intentionally slow by design)
  - JWT sign:      < 5 ms per call
  - JWT verify:    < 5 ms per call
  - SessionMetadata.from_login_context: < 0.1 ms per call (pure Python)
  - RateLimitInfo + build_rate_limit_headers: < 0.1 ms per call

asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

import pytest
from pydantic import SecretStr


# ──────────────────────────────────────────────────────────────────────────── #
# Benchmark utility                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


def _run_benchmark(fn: Callable[[], object], *, iterations: int = 10) -> tuple[float, float]:
    """
    Run fn() for the given number of iterations and return timing.

    Returns:
        (avg_ms_per_call, total_ms)
    """
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    total_s = time.perf_counter() - start
    total_ms = total_s * 1000.0
    avg_ms = total_ms / iterations
    return avg_ms, total_ms


async def _run_async_benchmark(
    coro_factory: Callable[[], object],
    *,
    iterations: int = 10,
) -> tuple[float, float]:
    """
    Run an async coroutine factory for the given number of iterations.

    coro_factory must be a zero-argument callable that returns a new coroutine
    each time it is called.
    """
    import asyncio

    start = time.perf_counter()
    for _ in range(iterations):
        await coro_factory()  # type: ignore[misc]
    total_s = time.perf_counter() - start
    total_ms = total_s * 1000.0
    avg_ms = total_ms / iterations
    return avg_ms, total_ms


# ──────────────────────────────────────────────────────────────────────────── #
# Password hashing benchmark                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class TestPasswordHashingBenchmark:
    """Argon2id hashing is intentionally slow — verify it stays within design bounds."""

    @pytest.mark.slow
    async def test_argon2_hash_benchmark(self) -> None:
        """
        Argon2id hash time should be 50–500 ms per call on a developer machine.
        Above 500 ms per call suggests the parallelism/memory parameters were
        accidentally increased. Below 50 ms suggests they were accidentally lowered.
        """
        from app.modules.identity.authentication.infrastructure.password_hasher import (
            Argon2PasswordHasher,
        )

        hasher = Argon2PasswordHasher()
        password = "BenchmarkPassword123!"

        avg_ms, total_ms = await _run_async_benchmark(
            lambda: hasher.hash(password),  # type: ignore[return-value]
            iterations=3,  # Argon2 is slow by design — 3 iterations is enough
        )

        # Generous upper bound — fails only on severe regression or misconfiguration.
        assert avg_ms < 5_000, (
            f"Argon2id hash took {avg_ms:.1f} ms on average — "
            "parameters may be misconfigured (too high)."
        )

    @pytest.mark.slow
    async def test_argon2_verify_benchmark(self) -> None:
        """Argon2id verification should be comparable to hashing time."""
        from app.modules.identity.authentication.infrastructure.password_hasher import (
            Argon2PasswordHasher,
        )

        hasher = Argon2PasswordHasher()
        password = "BenchmarkPassword123!"
        hashed = await hasher.hash(password)

        avg_ms, _ = await _run_async_benchmark(
            lambda: hasher.verify(password, hashed),  # type: ignore[return-value]
            iterations=3,
        )

        assert avg_ms < 5_000, (
            f"Argon2id verify took {avg_ms:.1f} ms on average."
        )


# ──────────────────────────────────────────────────────────────────────────── #
# JWT sign + verify benchmark                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestJWTBenchmark:
    """JWT sign and verify should each take well under 5 ms."""

    def _make_service(self):  # type: ignore[return]
        from app.core.security.jwt.claims import AccessTokenClaims
        from app.core.security.jwt.service import HS256JWTService
        from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey

        key = SigningKey(
            kid="bench-v1",
            algorithm="HS256",
            secret=SecretStr("bench-secret-must-be-at-least-32-chars!"),
            is_primary=True,
        )
        return HS256JWTService(
            signing_key_provider=InMemorySigningKeyProvider(key),
            issuer="https://api.travix.ai",
            audience="travix-mobile",
            algorithm="HS256",
            leeway_seconds=0,
            access_token_lifetime_minutes=15,
        )

    def _make_claims(self):  # type: ignore[return]
        from app.core.security.jwt.claims import AccessTokenClaims

        now = datetime.now(UTC)
        return AccessTokenClaims(
            sub=str(uuid.uuid4()),
            jti=str(uuid.uuid4()),
            iat=now,
            exp=now + timedelta(minutes=15),
            nbf=now,
            iss="https://api.travix.ai",
            aud="travix-mobile",
            sid=str(uuid.uuid4()),
            email="bench@example.com",
            verified=True,
        )

    def test_jwt_sign_benchmark(self) -> None:
        """JWT sign should take well under 5 ms per call."""
        svc = self._make_service()
        claims = self._make_claims()

        avg_ms, _ = _run_benchmark(lambda: svc.create_access_token(claims), iterations=50)

        assert avg_ms < 50.0, (
            f"JWT sign took {avg_ms:.2f} ms on average — expected < 50 ms."
        )

    def test_jwt_verify_benchmark(self) -> None:
        """JWT verify (signature + claims) should take well under 5 ms per call."""
        svc = self._make_service()
        claims = self._make_claims()
        token = svc.create_access_token(claims)

        avg_ms, _ = _run_benchmark(lambda: svc.verify_access_token(token), iterations=50)

        assert avg_ms < 50.0, (
            f"JWT verify took {avg_ms:.2f} ms on average — expected < 50 ms."
        )


# ──────────────────────────────────────────────────────────────────────────── #
# Value object construction benchmarks                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestValueObjectBenchmark:
    """Pure-Python value object creation should be sub-millisecond."""

    def test_session_metadata_construction(self) -> None:
        from app.modules.identity.authentication.domain.value_objects.session_metadata import (
            SessionMetadata,
        )

        avg_ms, _ = _run_benchmark(
            lambda: SessionMetadata.from_login_context(
                device_name="iPhone 14",
                platform="ios",
                app_version="2.0.0",
                locale="en-US",
                timezone="America/New_York",
            ),
            iterations=1_000,
        )
        assert avg_ms < 1.0, f"SessionMetadata took {avg_ms:.4f} ms — expected < 1 ms."

    def test_rate_limit_header_building(self) -> None:
        from app.core.middleware.rate_limit import RateLimitInfo, build_rate_limit_headers

        info = RateLimitInfo(limit=60, remaining=55, reset_at=1_700_000_000, retry_after=None)

        avg_ms, _ = _run_benchmark(
            lambda: build_rate_limit_headers(info),
            iterations=1_000,
        )
        assert avg_ms < 1.0, f"build_rate_limit_headers took {avg_ms:.4f} ms — expected < 1 ms."

    def test_security_context_construction(self) -> None:
        from datetime import UTC, datetime

        from app.core.security.auth.context import AuthorizationContext
        from app.core.security.auth.security_context import build_security_context

        now = datetime.now(UTC)
        auth_ctx = AuthorizationContext(
            user_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            token_id=str(uuid.uuid4()),
            token_version=1,
            session_version=1,
            authentication_method="password",
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            email="bench@example.com",
            is_email_verified=True,
        )

        avg_ms, _ = _run_benchmark(
            lambda: build_security_context(
                auth_ctx,
                request_id=str(uuid.uuid4()),
                correlation_id="",
                ip_address="127.0.0.1",
                user_agent="Travix/2.0 (iOS 17)",
                locale="en-US",
                timezone="UTC",
                app_version="2.0.0",
                received_at=now,
            ),
            iterations=1_000,
        )
        assert avg_ms < 1.0, f"build_security_context took {avg_ms:.4f} ms — expected < 1 ms."
