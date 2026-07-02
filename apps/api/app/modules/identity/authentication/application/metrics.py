"""
AuthenticationMetrics — interface for recording authentication operation outcomes.

An extension point only. No implementation is provided in this sprint.
Concrete implementations might publish to:
  - Prometheus / OpenTelemetry (TASK-3.x)
  - StatsD / Datadog (TASK-3.x)
  - Structured log sink (simple: count by parsing log lines)

Design:
  All methods are fire-and-forget coroutines returning None.
  Implementations MUST NOT raise — metric recording failures should be
  swallowed silently (logged at DEBUG level) so that a metrics backend
  outage never blocks authentication flows.

  If an implementation needs labels (e.g., "registration_source=google"),
  add keyword arguments with default None — do not change existing signatures.

Injection pattern (when an implementation exists):
  In infrastructure/dependencies.py:
    def get_authentication_metrics() -> AuthenticationMetrics:
        return PrometheusAuthMetrics(registry=get_metrics_registry())

  In the service:
    class LoginService:
        def __init__(self, ..., metrics: AuthenticationMetrics | None = None): ...
        async def execute(self, command) -> LoginResult:
            ...
            if self._metrics:
                await self._metrics.record_login_success(user_id=...)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthenticationMetrics(Protocol):
    """
    Interface for recording authentication operation counters and gauges.

    Implementations increment counters or publish gauge values to a metrics
    backend. All methods are async to allow non-blocking I/O to the backend.

    Error contract:
      Implementations must NOT raise exceptions. Wrap internal errors with
      a try/except and log at DEBUG level to avoid blocking auth flows.
    """

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    async def record_registration_success(
        self,
        *,
        user_id: str,
        source: str = "email",
    ) -> None:
        """
        Record a successful new user registration.

        Args:
            user_id: The newly created user's UUID string.
            source:  RegistrationSource string (e.g., "email", "google").
        """
        ...

    async def record_registration_failure(
        self,
        *,
        reason: str,
        source: str = "email",
    ) -> None:
        """
        Record a failed registration attempt.

        Args:
            reason: Error code string (e.g., "email_already_exists", "weak_password").
            source: RegistrationSource string.
        """
        ...

    # ------------------------------------------------------------------ #
    # Login                                                                #
    # ------------------------------------------------------------------ #

    async def record_login_success(
        self,
        *,
        user_id: str,
        authentication_method: str = "password",
    ) -> None:
        """
        Record a successful login.

        Args:
            user_id:               The authenticated user's UUID string.
            authentication_method: AuthenticationMethod string.
        """
        ...

    async def record_login_failure(
        self,
        *,
        reason: str,
        authentication_method: str = "password",
    ) -> None:
        """
        Record a failed login attempt.

        Args:
            reason:                Error code string (e.g., "invalid_credentials",
                                   "account_locked", "email_not_verified").
            authentication_method: AuthenticationMethod string.
        """
        ...

    # ------------------------------------------------------------------ #
    # Token refresh                                                        #
    # ------------------------------------------------------------------ #

    async def record_refresh_success(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> None:
        """Record a successful refresh token rotation."""
        ...

    async def record_refresh_failure(
        self,
        *,
        reason: str,
        session_id: str | None = None,
    ) -> None:
        """
        Record a failed refresh token rotation attempt.

        Args:
            reason:     Error code (e.g., "token_expired", "token_reuse").
            session_id: Session UUID string if known at failure time.
        """
        ...

    # ------------------------------------------------------------------ #
    # Logout                                                               #
    # ------------------------------------------------------------------ #

    async def record_logout(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> None:
        """Record a successful single-session logout."""
        ...

    # ------------------------------------------------------------------ #
    # Security events                                                      #
    # ------------------------------------------------------------------ #

    async def record_token_reuse(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> None:
        """
        Record a stolen-token reuse event.

        This is a high-severity security signal — the refresh token was
        presented after already being rotated. The session has been revoked.
        Triggers alerts in production monitoring (TASK-3.x).
        """
        ...

    async def record_account_locked(
        self,
        *,
        user_id: str,
        failed_attempts: int,
    ) -> None:
        """
        Record an account being temporarily locked due to repeated failures.

        Args:
            user_id:         The locked user's UUID string.
            failed_attempts: Number of consecutive failed login attempts.
        """
        ...
