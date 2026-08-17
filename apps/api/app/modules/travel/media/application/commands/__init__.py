"""Media application commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadMediaCommand:
    """Command to upload a new media item to a trip's collection."""

    trip_id: str
    file_name: str
    file_content: bytes
    mime_type: str
    uploaded_by: str


@dataclass(frozen=True)
class UpdateCaptionCommand:
    """Command to update the caption of a media item."""

    trip_id: str
    media_id: str
    caption: str | None
    requester_id: str


@dataclass(frozen=True)
class DeleteMediaCommand:
    """Command to soft-delete a media item from the collection."""

    trip_id: str
    media_id: str
    requester_id: str


@dataclass(frozen=True)
class AttachMediaToActivityCommand:
    """Command to link a media item to an itinerary activity."""

    trip_id: str
    media_id: str
    activity_id: str
    requester_id: str


@dataclass(frozen=True)
class AttachMediaToExpenseCommand:
    """Command to link a media item to an expense entry."""

    trip_id: str
    media_id: str
    expense_id: str
    requester_id: str
