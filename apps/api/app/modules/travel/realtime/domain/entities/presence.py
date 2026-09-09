"""Collaborator Presence Domain Entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class CollaboratorPresence:
    """Represents an active collaborator viewing/editing a trip in real-time."""

    user_id: str
    display_name: str
    role: str  # "owner" | "editor" | "viewer"
    joined_at: datetime
    client_id: str

    def to_dict(self) -> dict[str, str]:
        """Convert presence model to serializable dictionary."""
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "role": self.role,
            "joined_at": self.joined_at.isoformat(),
            "client_id": self.client_id,
        }
