"""
Password Security Ports — future-ready domain interfaces.

These ports are DOCUMENTED PLACEHOLDERS. The concrete adapters and the
application-layer wiring that calls them are deferred to a later task.

Defined here so that:
  1. The domain architecture is complete before infrastructure work begins.
  2. Future engineers know exactly which abstraction to implement — no design
     decisions are left implicit.
  3. The PasswordHasher adapter (TASK-2.3) can be reviewed against the full
     picture of what the password security subsystem will eventually look like.

Neither interface has any infrastructure dependency. Both are synchronous at
the domain level; async I/O wrappers live in the application layer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CompromisedPasswordChecker(Protocol):
    """
    Domain port: check whether a password appears in a breach corpus.

    Intended implementation: HaveIBeenPwned k-anonymity API.
      - Hash the candidate with SHA-1.
      - Send the first 5 hex characters to the HIBP range API.
      - Check whether the full hash appears in the response.
      - NEVER send the full password or hash to the external service.

    The concrete adapter (HibpCompromisedPasswordChecker) is an infrastructure
    concern and will be created in a dedicated task.  The application layer
    wraps the synchronous result in asyncio.to_thread() for non-blocking I/O.

    Security note:
      If the HIBP API is unavailable, the check MUST fail open (return False /
      "not compromised") rather than block registration.  Blocking on third-party
      availability is a denial-of-service vector.  Log the failure and continue.

    Usage (future application layer):
        checker: CompromisedPasswordChecker = HibpCompromisedPasswordChecker(...)
        if await asyncio.to_thread(checker.is_compromised, password):
            raise WeakPasswordError(violations=["Password has appeared in a data breach."])
    """

    def is_compromised(self, plain_password: str) -> bool:
        """
        Return True if the password is known to have appeared in a data breach.

        Must NEVER log, store, or transmit the plaintext password.
        Must use k-anonymity or a local corpus — never send the full password.
        Must return False (fail open) if the check cannot be completed.

        Args:
            plain_password: The candidate plaintext password. Treat as secret.

        Returns:
            True  — password is known-compromised (reject at the application layer).
            False — password not found in corpus OR check could not be completed.
        """
        ...


@runtime_checkable
class PasswordEntropyEvaluator(Protocol):
    """
    Domain port: estimate the information entropy of a password in bits.

    Intended implementation: zxcvbn (Dropbox's realistic password strength
    estimator), which accounts for dictionary words, keyboard patterns,
    and common substitutions — unlike naive character-class counting.

    The concrete adapter (ZxcvbnEntropyEvaluator) is an infrastructure concern.
    The application layer uses it to augment PasswordStrengthPolicy.get_violations()
    with an entropy-based message when the password is technically long enough
    but predictable (e.g., "correcthorsebatterystaple" has many characters but
    low structural entropy under zxcvbn's model).

    Relationship to PasswordStrengthPolicy:
      PasswordStrengthPolicy enforces HARD rules (length, character classes).
      PasswordEntropyEvaluator provides SOFT guidance ("this password is weak
      despite meeting length requirements").  The application layer combines
      both to give users actionable feedback.

    Usage (future application layer):
        evaluator: PasswordEntropyEvaluator = ZxcvbnEntropyEvaluator()
        bits = evaluator.entropy_bits(candidate)
        if bits < MINIMUM_ENTROPY_BITS:
            violations.append(f"Password is too predictable ({bits:.0f} bits entropy).")
    """

    def entropy_bits(self, plain_password: str) -> float:
        """
        Estimate the entropy of the password in bits.

        Higher is stronger. As a rough reference:
          < 28 bits  → very weak (crackable offline in minutes)
          28–35 bits → weak
          36–59 bits → reasonable
          ≥ 60 bits  → strong

        Must NEVER log or store the plaintext password.

        Args:
            plain_password: The candidate plaintext password. Treat as secret.

        Returns:
            Estimated entropy in bits (float ≥ 0).
        """
        ...

    def crack_time_seconds(self, plain_password: str) -> float:
        """
        Estimate offline crack time in seconds (at 10^10 guesses/second).

        Useful for generating human-readable "time-to-crack" messages
        in the UI rather than exposing raw entropy numbers to users.

        Args:
            plain_password: The candidate plaintext password. Treat as secret.

        Returns:
            Estimated offline crack time in seconds.
        """
        ...
