"""Service interfaces (Protocols) for the Media bounded context."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    """Abstract interface for storing raw media bytes."""

    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        mime_type: str,
    ) -> str:
        """
        Upload file content to storage and return the public HTTPS URL.

        Raises:
            InfrastructureError: if the upload fails.
        """
        ...

    async def delete_file(self, file_url: str) -> None:
        """
        Delete a file from storage.

        Raises:
            InfrastructureError: if deletion fails.
        """
        ...


@runtime_checkable
class ThumbnailGenerator(Protocol):
    """Abstract interface for generating media thumbnails."""

    async def generate_thumbnail(
        self,
        image_content: bytes,
        width: int,
        height: int,
        mime_type: str,
    ) -> bytes:
        """
        Resize and compress image content into a thumbnail.

        Returns the thumbnail bytes.
        """
        ...


@runtime_checkable
class VirusScanner(Protocol):
    """Abstract interface for scanning media files for malicious content."""

    async def scan_file(self, file_content: bytes) -> bool:
        """
        Scan a file for viruses.

        Returns:
            True if the file is safe/clean, False if a threat is detected.
        """
        ...


@runtime_checkable
class ImageMetadataExtractor(Protocol):
    """
    Abstract interface for extracting metadata (dimensions, resolution, exif, etc.)
    from images.
    """

    async def extract_metadata(
        self,
        file_content: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        """
        Parse image header/exif data and return metadata attributes.

        Returns key-value attributes like 'width', 'height', 'camera_model', etc.
        """
        ...
