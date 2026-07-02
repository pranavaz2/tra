"""
Authentication Domain Specifications.

Pure in-memory predicates that encode authentication business rules.
All specifications implement Specification[T] from the shared kernel.

These are NOT ClauseSpecification subclasses — they have no SQL translation.
SQL filtering for authentication queries (e.g., find active sessions) is
expressed directly in the repository implementations, which have access to
the ORM model columns.

Specifications here serve two purposes:
  1. In-memory filtering of domain objects (e.g., filtering a list of
     loaded sessions to find active ones).
  2. Explicit, named reification of business rules that can be composed
     with & and | operators and tested in isolation.

See app.shared.domain.specification for combinator operators.

Added in TASK-2.2:
  ReusablePasswordSpecification  — detects password reuse via PasswordHasher
  ExpiredPasswordSpecification   — detects expired passwords via PasswordExpiryPolicy
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.shared.domain.specification import Specification
from app.modules.identity.authentication.domain.entities.credential import AuthenticationCredential
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.services.password_hasher import PasswordHasher
from app.modules.identity.authentication.domain.services.password_policies import (
    PasswordExpiryPolicy,
    PasswordStrengthPolicy,
)
from app.modules.identity.authentication.domain.value_objects.email import is_valid_email_format
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash


class ValidEmailSpecification(Specification[str]):
    """
    Satisfied when a string is a syntactically valid email address.

    Uses the same regex as Email value object construction, so this
    specification and the value object always agree.

    Usage:
        spec = ValidEmailSpecification()
        if not spec.is_satisfied_by(user_input):
            raise InvalidEmailError(...)
    """

    def is_satisfied_by(self, candidate: str) -> bool:
        return is_valid_email_format(candidate)

    def __repr__(self) -> str:
        return "ValidEmailSpecification()"


class StrongPasswordSpecification(Specification[str]):
    """
    Satisfied when a plaintext password meets the configured strength policy.

    Delegates to PasswordStrengthPolicy.is_strong_enough() so the strength
    rules can change without modifying this specification. Inject the concrete
    policy implementation via the constructor.

    Changed in TASK-2.2: now accepts PasswordStrengthPolicy (supersedes the
    earlier PasswordPolicy which has been removed from policies.py).

    Usage:
        spec = StrongPasswordSpecification(policy=DefaultPasswordStrengthPolicy())
        if not spec.is_satisfied_by(plaintext_password):
            violations = policy.get_violations(plaintext_password)
            raise WeakPasswordError(violations=violations)
    """

    def __init__(self, policy: PasswordStrengthPolicy) -> None:
        self._policy = policy

    def is_satisfied_by(self, candidate: str) -> bool:
        return self._policy.is_strong_enough(candidate)

    def __repr__(self) -> str:
        return f"StrongPasswordSpecification(min_length={self._policy.minimum_length})"


class ActiveSessionSpecification(Specification[AuthenticationSession]):
    """
    Satisfied when an AuthenticationSession is neither expired nor revoked.

    Used to filter a list of loaded sessions to find those that are still
    valid (e.g., for the concurrent session count check).

    Usage:
        active_spec = ActiveSessionSpecification()
        active_sessions = list(active_spec.filter(all_user_sessions))
        if len(active_sessions) >= policy.max_concurrent_sessions:
            raise MaxSessionsExceededError(max_sessions=policy.max_concurrent_sessions)
    """

    def is_satisfied_by(self, candidate: AuthenticationSession) -> bool:
        return candidate.is_active

    def __repr__(self) -> str:
        return "ActiveSessionSpecification()"


class ReusablePasswordSpecification(Specification[str]):
    """
    Satisfied when a plaintext password has NOT been recently used.

    Checks the candidate against a list of historical PasswordHash values
    using PasswordHasher.verify (constant-time comparison). This specification
    lives in the domain because the RULE ("do not reuse recent passwords") is
    a business invariant — the IMPLEMENTATION (bcrypt.checkpw) is injected
    via the PasswordHasher port.

    Usage:
        spec = ReusablePasswordSpecification(
            hasher=injected_hasher,
            recent_hashes=credential.recent_password_hashes,  # from infrastructure
        )
        if not spec.is_satisfied_by(new_plain_password):
            raise PasswordReuseError(history_count=len(recent_hashes))

    Note:
        recent_hashes comes from the infrastructure layer (PasswordHistoryRepository
        or similar). The domain does not own the history — it only checks against
        what it is given.
    """

    def __init__(
        self,
        hasher: PasswordHasher,
        recent_hashes: list[PasswordHash],
    ) -> None:
        self._hasher = hasher
        self._recent_hashes = recent_hashes

    def is_satisfied_by(self, candidate: str) -> bool:
        """Return True if the password does NOT match any recent hash."""
        return not any(
            self._hasher.verify(candidate, stored_hash)
            for stored_hash in self._recent_hashes
        )

    def __repr__(self) -> str:
        return f"ReusablePasswordSpecification(history_depth={len(self._recent_hashes)})"


class ExpiredPasswordSpecification(Specification[AuthenticationCredential]):
    """
    Satisfied when a credential's password has exceeded its maximum allowed age.

    Uses PasswordExpiryPolicy.max_password_age to determine the threshold.
    A credential with password_changed_at = None is always considered expired
    (password was set outside the normal flow — force a reset).

    Usage:
        spec = ExpiredPasswordSpecification(policy=injected_expiry_policy)
        if spec.is_satisfied_by(credential):
            raise PasswordExpiredError()

    Applied by the application layer after every successful login to enforce
    periodic password rotation policies.
    """

    def __init__(self, policy: PasswordExpiryPolicy) -> None:
        self._policy = policy

    def is_satisfied_by(self, candidate: AuthenticationCredential) -> bool:
        """Return True if the password has expired and must be changed."""
        if candidate.password_changed_at is None:
            return True
        elapsed = datetime.now(UTC) - candidate.password_changed_at
        return elapsed > self._policy.max_password_age

    def __repr__(self) -> str:
        return f"ExpiredPasswordSpecification(max_age={self._policy.max_password_age})"
