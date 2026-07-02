"""
PasswordGenerator domain service interface.

Generates secure random passwords for use in:
  - Account recovery flows (one-time temporary passwords)
  - Admin-reset scenarios
  - Initial provisioned accounts

The generator is NOT responsible for validating the strength of the generated
password — it MUST produce passwords that satisfy the active PasswordStrengthPolicy
by construction. Any generated password that fails the policy is a bug in the
generator implementation, not in the policy.

Infrastructure adapters must use a cryptographically secure random source
(secrets.SystemRandom or equivalent — never random.Random).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordGenerator(Protocol):
    """
    Port for cryptographically secure password generation.

    Implementations should read PasswordComplexityPolicy at construction
    time and produce passwords that always satisfy it.

    Usage (application layer):
        temp_password = generator.generate()
        new_hash = hasher.hash(temp_password)
        credential.change_password(new_hash)
        # send temp_password to user via email — then discard it
    """

    def generate(self) -> str:
        """
        Generate a cryptographically secure random password.

        The generated password MUST:
          - Satisfy the current PasswordStrengthPolicy and PasswordComplexityPolicy.
          - Be produced from a cryptographically secure random source.
          - Have enough entropy to resist brute-force attack (≥ 128 bits effective).
          - Never be stored — hand it to the hasher and the notification service,
            then let it go out of scope.

        Returns:
            A plaintext random password string. Treat it as a secret;
            pass it to PasswordHasher.hash() immediately.

        Raises:
            PasswordGenerationError: if the generator cannot produce a
                password satisfying the policy (should be rare).
        """
        ...
