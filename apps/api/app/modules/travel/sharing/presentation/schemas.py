"""Sharing presentation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Standard success data envelope wrapper."""

    data: T
    model_config = ConfigDict(populate_by_name=True)


# ──────────────────────────────────────────────────────────────────────────── #
# Request schemas                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


class InviteMemberRequest(BaseModel):
    """Request schema for inviting a member to a trip collaboration."""

    invitee_email: EmailStr = Field(
        ...,
        description="Email address of the user to invite.",
        examples=["alice@example.com"],
    )
    role: Literal["editor", "viewer"] = Field(
        ...,
        description="Role to grant. Cannot be 'owner'.",
    )

    model_config = ConfigDict(extra="forbid")


class ChangeMemberRoleRequest(BaseModel):
    """Request schema for changing a member's role."""

    role: Literal["editor", "viewer"] = Field(
        ...,
        description="New role to assign. Cannot be 'owner'.",
    )

    model_config = ConfigDict(extra="forbid")


class PublicSharingRequest(BaseModel):
    """Request schema for toggling or rotating public sharing."""

    action: Literal["enable", "disable", "rotate"] = Field(
        ...,
        description=(
            "'enable' — turn on public sharing, "
            "'disable' — turn off public sharing, "
            "'rotate' — generate a new share token (public sharing must already be enabled)."
        ),
    )

    model_config = ConfigDict(extra="forbid")


# ──────────────────────────────────────────────────────────────────────────── #
# Response schemas                                                                #
# ──────────────────────────────────────────────────────────────────────────── #


class MemberResponse(BaseModel):
    """Response schema representing a TripMember."""

    id: str = Field(alias="member_id")
    user_id: str
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvitationResponse(BaseModel):
    """Response schema representing an Invitation."""

    id: str = Field(alias="invitation_id")
    invitee_email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CollaborationResponse(BaseModel):
    """Response schema representing a TripCollaboration."""

    id: str = Field(alias="collaboration_id")
    trip_id: str
    owner_id: str
    member_count: int
    is_public: bool
    share_token: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ShareTokenResponse(BaseModel):
    """Response schema returned when a share token is generated or rotated."""

    share_token: str
    is_public: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MemberListResponse(BaseModel):
    """Cursor-paginated list of members."""

    items: tuple[MemberResponse, ...]
    next_cursor: str | None
    has_more: bool
    limit: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvitationListResponse(BaseModel):
    """Cursor-paginated list of invitations."""

    items: tuple[InvitationResponse, ...]
    next_cursor: str | None
    has_more: bool
    limit: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
