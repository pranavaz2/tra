"""
Authentication Domain Service Policies — Session and Authentication.

Note: PasswordPolicy was REMOVED from this file in TASK-2.2.
It has been replaced by PasswordStrengthPolicy (a strict superset)
in domain/services/password_policies.py alongside the full set of
password lifecycle policies.

This file now contains only:
  SessionPolicy           → session lifetime and concurrency limits.
  AuthenticationPolicy    → login attempt limits and verification rules.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionPolicy(Protocol):
    """
    Rules governing session lifetime and concurrency.

    Applied by the application layer when creating and refreshing sessions.
    """

    @property
    def session_ttl(self) -> timedelta:
        """
        How long a session lives from creation.

        CLAUDE.md §11: refresh tokens have a 7-day expiry.
        """
        ...

    @property
    def max_concurrent_sessions(self) -> int:
        """
        Maximum number of active sessions a single user may hold.

        Attempting to create a session beyond this limit raises
        MaxSessionsExceededError.
        """
        ...

    @property
    def idle_timeout(self) -> timedelta:
        """
        How long a session may be idle before it is considered expired.

        A session's last_active_at must be within this window. Background
        jobs call session.expire() on sessions that exceed the idle timeout.
        """
        ...

    @property
    def refresh_window(self) -> timedelta:
        """
        How long before expiry a session may request a token refresh.

        A client that refreshes more than refresh_window before expiry is
        likely cycling tokens unnecessarily; this window prevents that.
        Set to timedelta(0) to disable the refresh window restriction.
        """
        ...


@runtime_checkable
class AuthenticationPolicy(Protocol):
    """
    Rules governing login attempt limiting and account verification.
    """

    @property
    def max_failed_attempts(self) -> int:
        """
        Number of failed login attempts allowed before the account is locked.

        Passed to AuthenticationCredential.record_failed_login().
        """
        ...

    @property
    def lockout_duration(self) -> timedelta:
        """
        How long an account remains locked after hitting max_failed_attempts.

        Passed to AuthenticationCredential.record_failed_login().
        """
        ...

    @property
    def require_email_verification(self) -> bool:
        """
        If True, users must verify their email before they can log in.

        Checked by the application layer; the domain records the verification
        state on AuthenticationCredential.is_email_verified.
        """
        ...
