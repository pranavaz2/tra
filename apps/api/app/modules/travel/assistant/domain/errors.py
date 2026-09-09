"""Assistant Domain Errors."""

from __future__ import annotations

from app.shared.domain.errors import TravixError


class AssistantError(TravixError):
    """Base error for all travel assistant operations."""


class ProposedActionNotFoundError(AssistantError):
    """Raised when a proposed action cannot be located."""

    def __init__(self, action_id: str) -> None:
        super().__init__(f"Proposed action '{action_id}' was not found.")
        self.action_id = action_id


class ActionAlreadyExecutedError(AssistantError):
    """Raised when trying to confirm or reject an action that is no longer pending."""

    def __init__(self, action_id: str, status: str) -> None:
        super().__init__(f"Proposed action '{action_id}' is already {status}.")
        self.action_id = action_id
        self.status = status


class ActionValidationError(AssistantError):
    """Raised when action payload fails validation rules."""


class ActionPermissionError(AssistantError):
    """Raised when user role is not permitted to confirm or apply mutations."""
