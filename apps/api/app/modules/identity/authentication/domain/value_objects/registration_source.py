"""
RegistrationSource — the channel through which a user account was created.

Stored on AuthenticationCredential at registration time. Immutable — the
source never changes after account creation. Used for analytics, onboarding
flow branching, and audit trails.

Future analytics queries:
  - Conversion rates by source
  - Retention cohort comparisons across sources
  - Invitation campaign attribution
"""

from __future__ import annotations

from enum import Enum


class RegistrationSource(str, Enum):
    """
    How the user account was originally created.

    EMAIL       — self-registration with email + password.
    GOOGLE      — account created via Google OAuth (TASK-3.x).
    APPLE       — account created via Sign in with Apple (TASK-3.x).
    PASSKEY     — account created with a FIDO2 passkey (TASK-4.x).
    INVITATION  — invited by another user or by an admin.
    """

    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"
    PASSKEY = "passkey"
    INVITATION = "invitation"
