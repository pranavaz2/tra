"""MemberRole enum."""

from __future__ import annotations

from enum import Enum


class MemberRole(str, Enum):
    """Role of a member within a shared trip collaboration."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"
