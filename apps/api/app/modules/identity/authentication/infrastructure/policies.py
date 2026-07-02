"""
Default policy implementations for the Authentication bounded context.

All policies are concrete classes that satisfy the corresponding domain
Protocol. Configuration values are read from application Settings at
construction time via the DI layer (infrastructure/dependencies.py).

Design:
  - Each class implements exactly one policy Protocol.
  - Values are stored as plain Python primitives on __init__ — no lazy
    Settings access inside property methods.
  - Classes are stateless after construction; they are safe to cache as
    singletons.
  - Tests may construct these classes directly with custom values, or use
    in-memory stubs that also satisfy the Protocol.
"""

from __future__ import annotations

from datetime import timedelta


class DefaultPasswordStrengthPolicy:
    """
    Password strength policy backed by application configuration.

    Implements PasswordStrengthPolicy from domain/services/password_policies.py.

    OWASP recommendations applied:
      - Minimum length 12 (not 8 — longer passphrases are stronger).
      - Maximum length 128 (Argon2id does not suffer bcrypt's 72-byte hard limit,
        but an upper bound prevents DoS via excessively long inputs).
      - No mandatory character classes by default — length + entropy suffice
        for Argon2id, and mandatory classes encourage predictable substitutions.
    """

    def __init__(
        self,
        *,
        minimum_length: int = 12,
        maximum_length: int = 128,
    ) -> None:
        self._minimum_length = minimum_length
        self._maximum_length = maximum_length

    @property
    def minimum_length(self) -> int:
        return self._minimum_length

    @property
    def maximum_length(self) -> int:
        return self._maximum_length

    def is_strong_enough(self, password: str) -> bool:
        return len(self.get_violations(password)) == 0

    def get_violations(self, password: str) -> list[str]:
        violations: list[str] = []
        length = len(password)
        if length < self._minimum_length:
            violations.append(
                f"Password must be at least {self._minimum_length} characters long "
                f"(currently {length})."
            )
        if length > self._maximum_length:
            violations.append(
                f"Password must not exceed {self._maximum_length} characters "
                f"(currently {length})."
            )
        return violations


class DefaultSessionPolicy:
    """
    Session lifetime and concurrency policy backed by application configuration.

    Implements SessionPolicy from domain/services/policies.py.
    """

    def __init__(
        self,
        *,
        session_ttl_days: int = 7,
        max_concurrent_sessions: int = 5,
        idle_timeout_days: int = 30,
        refresh_window_hours: int = 0,
    ) -> None:
        self._session_ttl = timedelta(days=session_ttl_days)
        self._max_concurrent = max_concurrent_sessions
        self._idle_timeout = timedelta(days=idle_timeout_days)
        self._refresh_window = timedelta(hours=refresh_window_hours)

    @property
    def session_ttl(self) -> timedelta:
        return self._session_ttl

    @property
    def max_concurrent_sessions(self) -> int:
        return self._max_concurrent

    @property
    def idle_timeout(self) -> timedelta:
        return self._idle_timeout

    @property
    def refresh_window(self) -> timedelta:
        return self._refresh_window


class DefaultAuthenticationPolicy:
    """
    Login attempt limits and email verification policy.

    Implements AuthenticationPolicy from domain/services/policies.py.
    """

    def __init__(
        self,
        *,
        max_failed_attempts: int = 5,
        lockout_duration_minutes: int = 15,
        require_email_verification: bool = True,
    ) -> None:
        self._max_failed_attempts = max_failed_attempts
        self._lockout_duration = timedelta(minutes=lockout_duration_minutes)
        self._require_email_verification = require_email_verification

    @property
    def max_failed_attempts(self) -> int:
        return self._max_failed_attempts

    @property
    def lockout_duration(self) -> timedelta:
        return self._lockout_duration

    @property
    def require_email_verification(self) -> bool:
        return self._require_email_verification
