"""
PermissionContext — extension point for future RBAC / ABAC.

Currently carries no fields. Exists so that:
  1. Route handlers that will need permissions can already declare the dependency.
  2. Adding roles, permissions, or scopes requires only this file and the
     dependency factory to change — no route handler signatures change.
  3. Feature modules can import PermissionContext today with a stable contract.

Planned fields (TASK-5.x — Role-Based Access Control):
    roles:         frozenset[str]  — user's assigned roles (e.g., {"admin", "user"})
    permissions:   frozenset[str]  — resolved permission strings (e.g., {"trips:read"})
    scopes:        frozenset[str]  — OAuth scope strings (e.g., {"openid", "trips"})
    feature_flags: frozenset[str]  — enabled feature flags for this user/session

Usage today (no-op, forward-compatible):
    from app.core.security.auth.permission_context import CurrentPermissionContext

    @router.delete("/trips/{trip_id}")
    async def delete_trip(
        ctx: CurrentSecurityContext,
        perms: CurrentPermissionContext,  # already wired, no-op until TASK-5.x
    ) -> Response:
        ...

Usage after TASK-5.x (same signature, new fields available):
    @router.delete("/trips/{trip_id}")
    async def delete_trip(ctx: CurrentSecurityContext, perms: CurrentPermissionContext):
        if "trips:delete" not in perms.permissions:
            raise ForbiddenError(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends

from app.core.security.auth.dependencies import RequireAuthentication


@dataclass(frozen=True)
class PermissionContext:
    """
    Resolved permission state for the current authenticated request.

    All fields default to empty collections. No RBAC logic exists yet.

    Future fields (add here when TASK-5.x ships RBAC):
        roles:         frozenset[str]  = frozenset()
        permissions:   frozenset[str]  = frozenset()
        scopes:        frozenset[str]  = frozenset()
        feature_flags: frozenset[str]  = frozenset()
    """

    # placeholder — frozenset fields have no default without field() in frozen dataclasses
    _placeholder: None = field(default=None, repr=False)

    def has_role(self, role: str) -> bool:
        """Return True if the user holds the given role. Always False until TASK-5.x."""
        return False

    def has_permission(self, permission: str) -> bool:
        """Return True if the resolved permissions include the given string. Always False until TASK-5.x."""
        return False

    def has_scope(self, scope: str) -> bool:
        """Return True if the token scope list includes the given scope. Always False until TASK-5.x."""
        return False


async def get_permission_context(
    auth: RequireAuthentication,  # noqa: ARG001  (will be used once RBAC is wired)
) -> PermissionContext:
    """
    FastAPI dependency: resolve the PermissionContext for the current request.

    Currently returns an empty PermissionContext. TASK-5.x will:
      1. Load the user's roles from the database (or a Redis role cache).
      2. Expand roles into their resolved permission strings.
      3. Extract OAuth scopes from the JWT claims.
      4. Evaluate active feature flags for the user/session.
      5. Return a populated PermissionContext.

    The dependency signature (auth: RequireAuthentication) is intentional —
    PermissionContext always requires an authenticated user.
    """
    return PermissionContext()


CurrentPermissionContext = Annotated[PermissionContext, Depends(get_permission_context)]
"""
Typed FastAPI dependency for the resolved permission context.

Currently a no-op. Declare it now in route handlers that will enforce
permissions in TASK-5.x — the signature will not need to change when RBAC ships.
"""
