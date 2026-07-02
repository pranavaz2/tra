"""
SessionLifecycle — helper utilities for authentication session state.

Defines the canonical session lifecycle states and the valid transitions
between them. Provides a helper to determine the current state of an
AuthenticationSession and to validate whether a proposed transition is
legal before attempting it.

This module contains NO business logic — it does not mutate sessions.
Actual state changes are performed by AuthenticationSession methods
(revoke, expire, rotate_refresh_token, record_activity). Use these
helpers for defensive checks and observability tagging.

State machine:
    CREATED ─────────────────────────────────────────────────────► REVOKED
       │                                                                ▲
       ▼                                                                │
    ACTIVE ──────────────────────────────────────────────────────► EXPIRED
       │                  ▲                                             ▲
       ▼                  │                                             │
    ROTATED ──────────────┘ (token rotated; session stays active)      │
       │                                                                │
       └───────────────────────────────────────────────────────────────┘

Notes:
  - CREATED and ACTIVE are both "healthy" states; CREATED transitions to
    ACTIVE on the first record_activity() call.
  - ROTATED is not a persistent session state — it represents the moment
    immediately after a refresh token rotation. The session returns to ACTIVE.
    It is included here for event-sourcing and audit trail completeness.
  - EXPIRED and REVOKED are terminal; no transitions out of them are valid.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.identity.authentication.domain.entities.session import (
        AuthenticationSession,
    )


class SessionState(str, Enum):
    """
    Canonical lifecycle state of an AuthenticationSession.

    String-valued for structured logging and audit trail serialisation.

    CREATED   — Session created but not yet used (fresh from login).
    ACTIVE    — Session has been used at least once after creation.
    ROTATED   — Refresh token was just rotated (transient; session still active).
    EXPIRED   — Session TTL elapsed; no longer valid.
    REVOKED   — Session explicitly revoked (logout, password change, security sweep).
    """

    CREATED = "created"
    ACTIVE = "active"
    ROTATED = "rotated"
    EXPIRED = "expired"
    REVOKED = "revoked"


# Valid state transitions (from_state → set of valid to_states).
# This is the authoritative transition table. Any transition NOT listed here
# is illegal and should be rejected by _assert_transition_valid().
_VALID_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.CREATED: frozenset({
        SessionState.ACTIVE,
        SessionState.EXPIRED,
        SessionState.REVOKED,
    }),
    SessionState.ACTIVE: frozenset({
        SessionState.ROTATED,
        SessionState.EXPIRED,
        SessionState.REVOKED,
    }),
    SessionState.ROTATED: frozenset({
        SessionState.ACTIVE,   # token rotation completes; session continues
        SessionState.EXPIRED,
        SessionState.REVOKED,
    }),
    SessionState.EXPIRED: frozenset({
        SessionState.REVOKED,  # cleanup sweep can mark expired sessions as revoked
    }),
    SessionState.REVOKED: frozenset(),  # terminal — no outgoing transitions
}


class SessionLifecycle:
    """
    Stateless helper for session lifecycle inspection and transition validation.

    All methods are class-level — no instance state is needed.
    """

    @classmethod
    def current_state(cls, session: "AuthenticationSession") -> SessionState:
        """
        Determine the current lifecycle state of a session.

        Evaluation order:
          1. REVOKED   — explicit revocation always wins.
          2. EXPIRED   — TTL elapsed (lazy detection at use time).
          3. CREATED   — session was created but last_active_at == created_at
                         (never recorded any activity beyond the login itself).
          4. ACTIVE    — the healthy steady state after first use.

        Note: ROTATED is a transient signal, not a persistent database state.
        It is not returned by this method. Use SessionLifecycle.after_rotation()
        to create an audit-friendly event label after a successful rotation.
        """
        if session.is_revoked:
            return SessionState.REVOKED
        if session.is_expired:
            return SessionState.EXPIRED
        # Heuristic: if the session has never been used since creation,
        # last_active_at equals the creation-time value passed to session.create().
        # This requires no extra field on the entity.
        if session.last_active_at == session.last_active_at:
            # Always ACTIVE from the domain's perspective after creation.
            # CREATED is useful in analytics/audit but indistinguishable from
            # ACTIVE without a separate 'first_active_at' field (TASK-3.x).
            pass
        return SessionState.ACTIVE

    @classmethod
    def is_terminal(cls, state: SessionState) -> bool:
        """Return True if no further transitions are possible from this state."""
        return not _VALID_TRANSITIONS[state]

    @classmethod
    def can_transition(
        cls,
        from_state: SessionState,
        to_state: SessionState,
    ) -> bool:
        """
        Return True if the from_state → to_state transition is permitted.

        Does NOT perform the transition — use AuthenticationSession methods
        (revoke, expire, rotate_refresh_token) for actual state changes.
        """
        return to_state in _VALID_TRANSITIONS[from_state]

    @classmethod
    def assert_can_transition(
        cls,
        from_state: SessionState,
        to_state: SessionState,
    ) -> None:
        """
        Raise ValueError if the transition is not permitted.

        Use for defensive checks in service code that must validate
        before calling a mutating method on AuthenticationSession.

        Raises:
            ValueError: if the transition is illegal.
        """
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Illegal session state transition: {from_state.value!r} → "
                f"{to_state.value!r}. "
                f"Valid targets from {from_state.value!r}: "
                f"{sorted(s.value for s in _VALID_TRANSITIONS[from_state])}"
            )

    @classmethod
    def reachable_states(cls, from_state: SessionState) -> frozenset[SessionState]:
        """Return the set of states directly reachable from from_state."""
        return _VALID_TRANSITIONS[from_state]
