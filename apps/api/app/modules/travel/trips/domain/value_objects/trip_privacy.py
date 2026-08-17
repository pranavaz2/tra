"""TripPrivacy enum — visibility of a Trip to other users."""

from __future__ import annotations

from enum import Enum


class TripPrivacy(str, Enum):
    """Controls who can discover and view a Trip."""

    PRIVATE = "private"      # Visible to owner and explicit collaborators only.
    LINK_ONLY = "link_only"  # Accessible to anyone who holds the share token.
    PUBLIC = "public"        # Discoverable by all users.
