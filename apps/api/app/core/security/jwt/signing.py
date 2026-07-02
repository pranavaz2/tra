"""
JWT signing key management.

SigningKey:                  Immutable value type for a single key with metadata.
InMemorySigningKeyProvider:  Holds one primary key and optional legacy keys for rotation.

Key rotation procedure:
  1. Generate a new secret, assign a new jwt_key_id in config.
  2. Deploy. InMemorySigningKeyProvider signs new tokens with the new key;
     tokens signed with the old key can still be verified if the old key is
     passed as an additional_key.
  3. After one access token lifetime (≤15 min), all old-key tokens have expired.
     Remove the old key from the provider configuration.

Future alternatives to InMemorySigningKeyProvider:
  - SecretsManagerSigningKeyProvider: reads from AWS Secrets Manager / Vault.
  - KMSSigningKeyProvider: uses AWS KMS for signing (key material never leaves KMS).
  Both implement the SigningKeyProvider protocol identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr


@dataclass(frozen=True)
class SigningKey:
    """
    A JWT signing key with rotation metadata.

    Attributes:
        kid:        Key identifier included in the JWT 'kid' header.
                    Receivers use this to look up the right verification key.
        algorithm:  Signing algorithm — "HS256" (current) or future "RS256".
        secret:     Raw key material (HMAC secret or PEM-encoded private key).
                    Wrapped in SecretStr so it never appears in repr/logs.
        is_primary: True for the key currently used to sign new tokens.
                    False for legacy keys kept for verification during rotation.
        not_after:  When this key should stop being used for signing.
                    None means the key is valid indefinitely for verification.
                    Set this during rotation to signal the key is being retired.
    """

    kid: str
    algorithm: str
    secret: SecretStr
    is_primary: bool
    not_after: datetime | None = None


class InMemorySigningKeyProvider:
    """
    Signing key provider backed by in-process memory.

    Suitable for single-instance deployments where the key is loaded from
    application settings at startup. Supports key rotation via additional_keys.

    Thread safety: read-only after construction — safe for concurrent access.
    """

    def __init__(self, primary: SigningKey, *additional_keys: SigningKey) -> None:
        """
        Args:
            primary:          The current signing key. Must have is_primary=True.
            *additional_keys: Legacy keys kept for verification during key rotation.
                              None of these should have is_primary=True.

        Raises:
            ValueError: if primary.is_primary is False, or if any two keys share a kid.
        """
        if not primary.is_primary:
            raise ValueError(
                f"The primary SigningKey (kid={primary.kid!r}) must have is_primary=True."
            )
        self._primary = primary
        self._all_keys: dict[str, SigningKey] = {primary.kid: primary}
        for key in additional_keys:
            if key.kid in self._all_keys:
                raise ValueError(
                    f"Duplicate key ID {key.kid!r}. Each key must have a unique kid."
                )
            self._all_keys[key.kid] = key

    def get_signing_key(self) -> SigningKey:
        """Return the primary signing key for encoding new tokens."""
        return self._primary

    def get_verification_keys(self, kid: str | None) -> list[SigningKey]:
        """
        Return the key(s) to use for verifying a token.

        Args:
            kid: Key identifier from the JWT header. Pass None to get all keys
                 (fallback for tokens without a kid header, not recommended).

        Returns:
            List containing the matching key, or empty list if not found.
        """
        if kid is None:
            return list(self._all_keys.values())
        key = self._all_keys.get(kid)
        return [key] if key is not None else []
