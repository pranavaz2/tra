"""
Password Domain Service Policies.

Configurable, injectable rules for every aspect of the password lifecycle.
All are Protocols — infrastructure provides concrete implementations that
read their configuration from Pydantic settings (environment variables).

Policy map:
  PasswordStrengthPolicy     → Is this password strong enough to be accepted?
  PasswordComplexityPolicy   → What character classes does a password need?
  PasswordHistoryPolicy      → How many past passwords must we remember?
  PasswordReusePolicy        → Can a password be reused, and after how long?
  PasswordExpiryPolicy       → Does a password have a maximum age?
  CredentialRotationPolicy   → When must the entire credential set be rotated?

Replaces the earlier PasswordPolicy (which is removed from policies.py).
The new PasswordStrengthPolicy is a strict superset of that interface.

Design:
  - All policies use @runtime_checkable Protocol.
  - Properties return primitive Python types (int, bool, timedelta, list[str]).
  - No Pydantic, no FastAPI, no SQLAlchemy anywhere in this file.
  - Policies are injected — the domain never imports a concrete policy.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordStrengthPolicy(Protocol):
    """
    Defines what constitutes an acceptable password.

    This is the primary gate for password validation. Before any password is
    hashed and stored, the application layer calls is_strong_enough() or
    get_violations() to decide whether to proceed.

    Supersedes the earlier PasswordPolicy interface.
    """

    @property
    def minimum_length(self) -> int:
        """Minimum character count. Recommended: ≥ 12."""
        ...

    @property
    def maximum_length(self) -> int:
        """
        Maximum character count.

        Prevents DoS via extremely long passwords that exhaust the bcrypt/Argon2
        cost function. Recommended: 72 for bcrypt (hard limit), 128 for Argon2.
        """
        ...

    def is_strong_enough(self, password: str) -> bool:
        """Return True if the password satisfies all strength rules."""
        ...

    def get_violations(self, password: str) -> list[str]:
        """
        Return human-readable violation strings for a failing password.

        Empty list → password is acceptable.
        Non-empty list → password fails; each string describes one violation.
        """
        ...


@runtime_checkable
class PasswordComplexityPolicy(Protocol):
    """
    Defines required character-class composition for passwords.

    Kept separate from PasswordStrengthPolicy so that a strength policy
    implementation can delegate complexity checks here without hard-coding them.
    """

    @property
    def requires_uppercase(self) -> bool:
        """At least one uppercase letter (A-Z) required."""
        ...

    @property
    def requires_lowercase(self) -> bool:
        """At least one lowercase letter (a-z) required."""
        ...

    @property
    def requires_digits(self) -> bool:
        """At least one numeric digit (0-9) required."""
        ...

    @property
    def requires_special_chars(self) -> bool:
        """At least one special character (!, @, #, etc.) required."""
        ...

    @property
    def allowed_special_chars(self) -> str:
        """
        The set of special characters that count toward requires_special_chars.

        Implementations typically return something like '!@#$%^&*()-_=+[]{}|;:,.<>?'
        """
        ...

    @property
    def min_unique_chars(self) -> int:
        """Minimum number of distinct characters. Prevents 'aaaaaaaa1!' type passwords."""
        ...


@runtime_checkable
class PasswordHistoryPolicy(Protocol):
    """
    Defines how many past password hashes to retain per credential.

    The stored hashes are used by ReusablePasswordSpecification (via
    PasswordHasher.verify) to detect reuse before the password is changed.
    """

    @property
    def max_history_count(self) -> int:
        """
        Number of previous password hashes to remember per user.

        Example: 5 means a user cannot reuse any of their last 5 passwords.
        Set to 0 to disable history checks.
        """
        ...

    @property
    def history_retention_period(self) -> timedelta:
        """
        Maximum age of a history entry that is still checked for reuse.

        If a previous password was used more than this duration ago, it
        is no longer checked even if it is within max_history_count entries.
        Set to timedelta.max to disable age-based exclusion.
        """
        ...


@runtime_checkable
class PasswordReusePolicy(Protocol):
    """
    Defines the minimum time that must elapse before a password can be reused.

    This operates at the time-dimension of history: even if a password is not
    in the recent hash history, it must have been retired long enough ago.
    """

    @property
    def min_age_before_reuse(self) -> timedelta:
        """
        Minimum elapsed time before a retired password can be used again.

        Example: timedelta(days=365) means a password cannot be reused
        within one year of being retired.
        Set to timedelta(0) to disable minimum-age enforcement.
        """
        ...


@runtime_checkable
class PasswordExpiryPolicy(Protocol):
    """
    Defines the maximum lifetime of a password before forced rotation.

    Used by ExpiredPasswordSpecification to determine if a credential's
    password has exceeded its allowed age and must be changed.
    """

    @property
    def max_password_age(self) -> timedelta:
        """
        Maximum time a password may be used before it expires.

        Example: timedelta(days=90) for a 90-day rotation policy.
        Set to timedelta.max to disable expiry enforcement.
        """
        ...

    @property
    def expiry_warning_period(self) -> timedelta:
        """
        How far before expiry to begin warning the user.

        Example: timedelta(days=14) means warnings start 14 days before expiry.
        """
        ...


@runtime_checkable
class CredentialRotationPolicy(Protocol):
    """
    Defines conditions that trigger a FORCED credential rotation event.

    Rotation differs from expiry: expiry is time-based; rotation is triggered
    by security events (breach detection, policy tightening, algorithm upgrade).

    The application layer checks this policy after every successful login
    and forces a password change if required.
    """

    def requires_rotation(self, *, days_since_last_change: int, algorithm_needs_upgrade: bool) -> bool:
        """
        Return True if the credential must be rotated before proceeding.

        Args:
            days_since_last_change:   How many days since the password was
                                      last changed.
            algorithm_needs_upgrade:  True if PasswordHasher.needs_rehash()
                                      returned True for the stored hash.
                                      A rotation is required for algorithm
                                      upgrades that cannot be done transparently
                                      (e.g., migrating from plaintext SHA1).

        Returns:
            True if the user MUST change their password before they can
            access the application. The application layer enforces this
            by returning a 403 with a specific error code.
        """
        ...

    @property
    def rotation_grace_period(self) -> timedelta:
        """
        How long a user has to complete a forced rotation before their
        account is locked.

        Set to timedelta(0) to enforce immediate rotation with no grace period.
        """
        ...
