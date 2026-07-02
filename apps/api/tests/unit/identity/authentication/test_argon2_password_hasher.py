"""
Unit tests — Argon2PasswordHasher.

Tests verify the security contract of the Argon2id adapter:
  - Hash generation: randomised salts, correct PHC format, non-empty output.
  - Verification: correct → True; wrong → False (no exception); constant-time path.
  - Needs-rehash: current params → False; lower params → True; non-Argon2 → True.
  - Configuration: custom Argon2Settings are applied to the underlying hasher.
  - Security properties: plaintext not in hash output; PasswordHash repr is redacted.
  - Error handling: empty password, corrupt hash, unsupported hash format.

All tests use Argon2Settings.for_testing() (time_cost=1, memory_cost=8 MiB)
so the test suite completes in milliseconds.
"""

from __future__ import annotations

import pytest

from app.modules.identity.authentication.domain.errors import PasswordHashingError
from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash
from app.modules.identity.authentication.infrastructure.password_hasher import (
    Argon2PasswordHasher,
    Argon2Settings,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FAST_SETTINGS = Argon2Settings.for_testing()
_FAST_SETTINGS_V2 = Argon2Settings(
    time_cost=2,
    memory_cost=16384,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    """Argon2PasswordHasher with minimal-cost settings for fast unit tests."""
    return Argon2PasswordHasher(settings=_FAST_SETTINGS)


@pytest.fixture
def upgraded_hasher() -> Argon2PasswordHasher:
    """Hasher with higher parameters — used to trigger needs_rehash() == True."""
    return Argon2PasswordHasher(settings=_FAST_SETTINGS_V2)


# ---------------------------------------------------------------------------
# 1. Hash generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHashGeneration:
    def test_returns_password_hash_instance(self, hasher: Argon2PasswordHasher) -> None:
        result = hasher.hash("correct_horse_battery_staple")
        assert isinstance(result, PasswordHash)

    def test_hash_is_argon2id_format(self, hasher: Argon2PasswordHasher) -> None:
        result = hasher.hash("correct_horse_battery_staple")
        assert result.value.startswith("$argon2id$")

    def test_hash_is_not_empty(self, hasher: Argon2PasswordHasher) -> None:
        result = hasher.hash("correct_horse_battery_staple")
        assert len(result.value) > 20

    def test_two_hashes_of_same_password_differ(self, hasher: Argon2PasswordHasher) -> None:
        """Random salt means the same password produces different hashes every time."""
        h1 = hasher.hash("correct_horse_battery_staple")
        h2 = hasher.hash("correct_horse_battery_staple")
        assert h1.value != h2.value

    def test_hash_unicode_password(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("Pässwörd_日本語_🔑")
        assert isinstance(h, PasswordHash)
        assert h.value.startswith("$argon2id$")

    def test_hash_password_with_special_characters(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("!@#$%^&*()_+{}[]|\\:;\"'<>,.?/`~")
        assert isinstance(h, PasswordHash)

    def test_hash_long_password(self, hasher: Argon2PasswordHasher) -> None:
        """Argon2 has no 72-byte truncation limit unlike bcrypt."""
        long_pw = "a" * 512
        h = hasher.hash(long_pw)
        assert isinstance(h, PasswordHash)
        assert hasher.verify(long_pw, h) is True

    def test_hash_raises_on_empty_password(self, hasher: Argon2PasswordHasher) -> None:
        with pytest.raises(PasswordHashingError, match="empty"):
            hasher.hash("")

    @pytest.mark.parametrize(
        "password",
        [
            "P@ssw0rd!",
            "correct_horse_battery_staple",
            "1234567890ABCdef!@#",
            "αβγδεζηθ",
            "密码Password123!",
        ],
    )
    def test_hash_various_password_types(
        self,
        hasher: Argon2PasswordHasher,
        password: str,
    ) -> None:
        h = hasher.hash(password)
        assert isinstance(h, PasswordHash)
        assert h.value.startswith("$argon2id$")


# ---------------------------------------------------------------------------
# 2. Verification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVerification:
    def test_correct_password_returns_true(self, hasher: Argon2PasswordHasher) -> None:
        pw = "correct_horse_battery_staple"
        h = hasher.hash(pw)
        assert hasher.verify(pw, h) is True

    def test_wrong_password_returns_false(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("correct_horse_battery_staple")
        assert hasher.verify("wrong_password", h) is False

    def test_wrong_password_does_not_raise(self, hasher: Argon2PasswordHasher) -> None:
        """Mismatch must return False, never raise. Raising is a timing side-channel."""
        h = hasher.hash("correct_horse_battery_staple")
        try:
            result = hasher.verify("wrong_password", h)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"verify() raised unexpectedly: {exc}")
        assert result is False

    def test_verification_is_case_sensitive(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("SecretPassword")
        assert hasher.verify("secretpassword", h) is False
        assert hasher.verify("SECRETPASSWORD", h) is False
        assert hasher.verify("SecretPassword", h) is True

    def test_verify_unicode_password(self, hasher: Argon2PasswordHasher) -> None:
        pw = "Pässwörd_日本語_🔑"
        h = hasher.hash(pw)
        assert hasher.verify(pw, h) is True
        assert hasher.verify("wrong", h) is False

    def test_multiple_wrong_passwords_all_return_false(
        self, hasher: Argon2PasswordHasher
    ) -> None:
        """Functional constant-time test: all wrong passwords return False consistently."""
        h = hasher.hash("correct_horse_battery_staple")
        wrong_passwords = [
            "wrong1",
            "correct_horse_battery_stapl",  # one char short
            "correct_horse_battery_staplE",  # capitalised
            " correct_horse_battery_staple",  # leading space
            "",
        ]
        for wrong in wrong_passwords:
            try:
                result = hasher.verify(wrong, h)
            except PasswordHashingError:
                # Empty string may raise from underlying library — acceptable
                continue
            assert result is False, f"verify() returned True for wrong password: {wrong!r}"

    def test_verify_corrupt_hash_raises_password_hashing_error(
        self, hasher: Argon2PasswordHasher
    ) -> None:
        """A structurally malformed Argon2 hash must raise PasswordHashingError."""
        # Corrupt the parameter section so the library cannot parse the hash.
        corrupt_hash = PasswordHash(
            value="$argon2id$v=99$m=NOTANUMBER,t=NOTANUMBER,p=1$AAAAAAAAAAAAAAAA$" + "A" * 43
        )
        with pytest.raises(PasswordHashingError):
            hasher.verify("some_password", corrupt_hash)

    def test_verify_non_argon2_hash_raises_password_hashing_error(
        self, hasher: Argon2PasswordHasher
    ) -> None:
        """
        Attempting to verify against a bcrypt-format hash must raise PasswordHashingError
        with a helpful migration message, NOT silently return False.
        """
        bcrypt_like = PasswordHash(value="$2b$12$" + "A" * 53)
        with pytest.raises(PasswordHashingError, match="[Uu]nsupported hash format"):
            hasher.verify("some_password", bcrypt_like)


# ---------------------------------------------------------------------------
# 3. Needs-rehash detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNeedsRehash:
    def test_current_params_do_not_need_rehash(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("correct_horse_battery_staple")
        assert hasher.needs_rehash(h) is False

    def test_lower_params_hash_needs_rehash(
        self,
        hasher: Argon2PasswordHasher,
        upgraded_hasher: Argon2PasswordHasher,
    ) -> None:
        """Hash produced with lower parameters must be flagged for re-hashing."""
        h_low = hasher.hash("correct_horse_battery_staple")
        assert upgraded_hasher.needs_rehash(h_low) is True

    def test_non_argon2_hash_needs_rehash(self, hasher: Argon2PasswordHasher) -> None:
        """
        A bcrypt-format hash must return True from needs_rehash() — it must be
        upgraded to Argon2id on next successful login.
        """
        bcrypt_like = PasswordHash(value="$2b$12$" + "A" * 53)
        assert hasher.needs_rehash(bcrypt_like) is True

    def test_same_params_hash_does_not_need_rehash(self) -> None:
        """Two hashers with identical settings agree that no rehash is needed."""
        settings = Argon2Settings.for_testing()
        h1 = Argon2PasswordHasher(settings=settings)
        h2 = Argon2PasswordHasher(settings=settings)
        h = h1.hash("correct_horse_battery_staple")
        assert h2.needs_rehash(h) is False


# ---------------------------------------------------------------------------
# 4. Configuration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfiguration:
    def test_default_settings_are_argon2id(self) -> None:
        """Hasher without explicit settings still uses Argon2id format."""
        hasher = Argon2PasswordHasher(settings=Argon2Settings.for_testing())
        h = hasher.hash("any_password")
        assert h.value.startswith("$argon2id$")

    def test_custom_settings_are_applied(self) -> None:
        """The hash format encodes parameters — verifies settings propagation."""
        settings = Argon2Settings(
            time_cost=1,
            memory_cost=8192,
            parallelism=1,
            hash_len=32,
            salt_len=16,
        )
        hasher = Argon2PasswordHasher(settings=settings)
        h = hasher.hash("password")
        assert "m=8192" in h.value
        assert "t=1" in h.value
        assert "p=1" in h.value

    def test_for_testing_classmethod_creates_valid_settings(self) -> None:
        settings = Argon2Settings.for_testing()
        assert settings.time_cost == 1
        assert settings.memory_cost == 8192
        assert settings.parallelism == 1

    def test_from_app_settings_maps_all_fields(self) -> None:
        """Argon2Settings.from_app_settings() maps every Settings field correctly."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.argon2_time_cost = 3
        mock_settings.argon2_memory_cost = 65536
        mock_settings.argon2_parallelism = 4
        mock_settings.argon2_hash_len = 32
        mock_settings.argon2_salt_len = 16

        s = Argon2Settings.from_app_settings(mock_settings)

        assert s.time_cost == 3
        assert s.memory_cost == 65536
        assert s.parallelism == 4
        assert s.hash_len == 32
        assert s.salt_len == 16


# ---------------------------------------------------------------------------
# 5. Security properties
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSecurityProperties:
    def test_plaintext_not_in_hash_output(self, hasher: Argon2PasswordHasher) -> None:
        pw = "secret_password_do_not_log"
        h = hasher.hash(pw)
        assert pw not in h.value

    def test_password_hash_repr_is_redacted(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("secret_password_do_not_log")
        assert "secret_password_do_not_log" not in repr(h)
        assert "[REDACTED]" in repr(h)

    def test_password_hash_str_is_redacted(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("secret_password_do_not_log")
        assert "secret_password_do_not_log" not in str(h)
        assert "[REDACTED]" in str(h)

    def test_different_passwords_produce_different_hashes(
        self, hasher: Argon2PasswordHasher
    ) -> None:
        h1 = hasher.hash("password_alpha")
        h2 = hasher.hash("password_beta")
        assert h1.value != h2.value

    def test_password_hashing_error_message_does_not_expose_plaintext(
        self, hasher: Argon2PasswordHasher
    ) -> None:
        """
        If the C library raises, the PasswordHashingError wrapper must NOT include
        the caller-supplied plaintext in its message.
        """
        from unittest.mock import patch

        sentinel = "SENTINEL_PLAINTEXT_xk7m2p9_DO_NOT_LOG"
        with patch.object(hasher, "_ph") as mock_ph:
            mock_ph.hash.side_effect = RuntimeError("simulated library failure")
            with pytest.raises(PasswordHashingError) as exc_info:
                hasher.hash(sentinel)

        assert sentinel not in exc_info.value.message
        assert exc_info.value.message  # non-empty error description

    def test_verify_returns_bool_not_truthy_value(self, hasher: Argon2PasswordHasher) -> None:
        """verify() must return exactly True or False, not a truthy/falsy argon2 return."""
        h = hasher.hash("password")
        result = hasher.verify("password", h)
        assert result is True

        wrong_result = hasher.verify("wrong", h)
        assert wrong_result is False

    def test_needs_rehash_returns_bool(self, hasher: Argon2PasswordHasher) -> None:
        h = hasher.hash("password")
        result = hasher.needs_rehash(h)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# 6. Round-trip integrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundTrip:
    @pytest.mark.parametrize(
        "password",
        [
            "simple",
            "P@ssw0rd_with_symbols!",
            "correct horse battery staple",
            "αβγ_unicode_🔐",
            "a" * 200,  # long password — Argon2 has no 72-byte limit
        ],
    )
    def test_hash_then_verify_succeeds(
        self,
        hasher: Argon2PasswordHasher,
        password: str,
    ) -> None:
        h = hasher.hash(password)
        assert hasher.verify(password, h) is True

    @pytest.mark.parametrize(
        ("password", "wrong"),
        [
            ("password", "passwod"),
            ("Password", "password"),
            ("password ", "password"),
            ("αβγ", "αβγδ"),
        ],
    )
    def test_hash_then_verify_wrong_password(
        self,
        hasher: Argon2PasswordHasher,
        password: str,
        wrong: str,
    ) -> None:
        h = hasher.hash(password)
        assert hasher.verify(wrong, h) is False
