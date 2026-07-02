"""
AuthenticationMethod — how the user authenticated.

Used in session records, JWT claims, and the authorization context.
String-valued so it can be stored in the database and JWT payload
without a separate mapping layer.

Current active value: PASSWORD
Future values: GOOGLE, APPLE, PASSKEY, MAGIC_LINK

Backward compatibility: any unknown string decoded from a legacy JWT
falls back to PASSWORD in the infrastructure deserialization layer.
"""

from __future__ import annotations

from enum import Enum


class AuthenticationMethod(str, Enum):
    """
    How the user's identity was established at login time.

    Values are lowercase strings. The JWT 'authentication_method' claim
    carries the string value (not the enum name). Compare with
    AuthenticationMethod("google") or AuthenticationMethod.GOOGLE.

    PASSWORD   — email + password verified by Argon2id hash comparison.
    GOOGLE     — OAuth 2.0 via Google Identity (TASK-3.x).
    APPLE      — Sign in with Apple (TASK-3.x).
    PASSKEY    — FIDO2/WebAuthn passkey (TASK-4.x).
    MAGIC_LINK — one-time email link, passwordless (TASK-3.x).
    """

    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"
    PASSKEY = "passkey"
    MAGIC_LINK = "magic_link"
