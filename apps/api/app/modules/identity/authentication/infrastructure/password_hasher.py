"""
Argon2id Password Hasher — infrastructure adapter.

Implements the PasswordHasher domain port using argon2-cffi.
Selected as the canonical hashing algorithm per ADR-004.

Security properties guaranteed by this adapter:
  - Random per-password salt (128-bit, managed by argon2-cffi).
  - Constant-time verification (VerifyMismatchError path never short-circuits).
  - Plaintext password is NEVER logged, stored, or present in any exception message.
  - PasswordHash repr is always "[REDACTED]" — enforced by the value object.
  - Parameters are read from application settings, not hardcoded.
  - Non-Argon2 hashes (e.g., bcrypt migration) detected in needs_rehash().
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type as _Argon2Type

from app.config import Settings, get_settings
from app.modules.identity.authentication.domain.errors import PasswordHashingError
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Argon2Settings:
    """
    Argon2id tuning parameters.

    Production: built from app Settings via from_app_settings().
    Tests: use for_testing() for fast low-memory parameters.
    """

    time_cost: int = 3
    memory_cost: int = 65536  # 64 MiB in KiB
    parallelism: int = 4
    hash_len: int = 32  # 256-bit output
    salt_len: int = 16  # 128-bit salt

    @classmethod
    def from_app_settings(cls, settings: Settings) -> Argon2Settings:
        return cls(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_len,
            salt_len=settings.argon2_salt_len,
        )

    @classmethod
    def for_testing(cls) -> Argon2Settings:
        """Minimal-cost settings for fast unit tests. INSECURE — never use in production."""
        return cls(
            time_cost=1,
            memory_cost=8192,  # 8 MiB — enough to hash quickly in test suites
            parallelism=1,
            hash_len=32,
            salt_len=16,
        )


class Argon2PasswordHasher:
    """
    Production Argon2id implementation of the PasswordHasher domain port.

    Thread-safe: argon2-cffi's PasswordHasher is stateless between calls
    (the C library allocates per-call). A single instance may be shared
    across requests.

    Exception contract:
      hash()        — raises PasswordHashingError for any failure; never logs plaintext.
      verify()      — returns False on mismatch; raises PasswordHashingError for
                      corrupt/incompatible hashes or library failures.
      needs_rehash() — returns True for non-Argon2 hashes (algorithm migration);
                      raises PasswordHashingError only for unexpected library errors.
    """

    def __init__(self, settings: Argon2Settings | None = None) -> None:
        params = settings or Argon2Settings()
        self._ph = _Argon2Hasher(
            type=_Argon2Type.ID,  # Argon2id — ADR-004
            time_cost=params.time_cost,
            memory_cost=params.memory_cost,
            parallelism=params.parallelism,
            hash_len=params.hash_len,
            salt_len=params.salt_len,
        )

    def hash(self, plain_password: str) -> PasswordHash:
        """
        Hash a plaintext password with Argon2id.

        Raises:
            PasswordHashingError: if the password is empty or the library fails.
        """
        if not plain_password:
            raise PasswordHashingError("Password must not be empty.")
        try:
            return PasswordHash(value=self._ph.hash(plain_password))
        except Exception as exc:
            raise PasswordHashingError(
                "Argon2id hashing operation failed.",
                cause=exc,
            ) from exc

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        """
        Verify a plaintext password against a stored Argon2id hash.

        Uses constant-time comparison internally (argon2-cffi C extension).
        Returns False — never raises — when the password is simply wrong.

        Raises:
            PasswordHashingError: for corrupt or incompatible (non-Argon2) hashes,
                or for unexpected library failures.
        """
        try:
            return self._ph.verify(password_hash.value, plain_password)
        except VerifyMismatchError:
            return False
        except VerificationError as exc:
            raise PasswordHashingError(
                "Argon2id hash verification failed — the stored hash may be corrupt.",
                cause=exc,
            ) from exc
        except InvalidHashError as exc:
            raise PasswordHashingError(
                "Unsupported hash format. "
                "If migrating from a different algorithm, use MigratingPasswordHasher.",
                cause=exc,
            ) from exc
        except Exception as exc:
            raise PasswordHashingError(
                "Unexpected error during password verification.",
                cause=exc,
            ) from exc

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        """
        Return True if the hash should be upgraded on next successful login.

        Returns True for:
          - Hashes produced with lower time_cost, memory_cost, or parallelism
            than the current settings (parameter upgrade path).
          - Hashes in a non-Argon2 format (e.g., bcrypt — algorithm migration path).

        Raises:
            PasswordHashingError: for unexpected library errors only.
        """
        try:
            return self._ph.check_needs_rehash(password_hash.value)
        except InvalidHashError:
            # Non-Argon2 hashes (bcrypt, scrypt, etc.) always need upgrading.
            # This is the expected path during algorithm migration, not an error.
            return True
        except Exception as exc:
            raise PasswordHashingError(
                "Failed to determine whether the password hash needs upgrading.",
                cause=exc,
            ) from exc


@lru_cache(maxsize=1)
def _build_default_hasher() -> Argon2PasswordHasher:
    """Singleton hasher built from application settings. Called once at startup."""
    settings = Argon2Settings.from_app_settings(get_settings())
    logger.info(
        "Argon2PasswordHasher initialised",
        extra={
            "time_cost": settings.time_cost,
            "memory_cost_kib": settings.memory_cost,
            "parallelism": settings.parallelism,
            "hash_len": settings.hash_len,
        },
    )
    return Argon2PasswordHasher(settings=settings)
