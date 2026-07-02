"""
SessionMetadata — immutable device and locale context attached to a session.

Captured at login time from client-reported headers and request body fields.
Never updated after session creation (except last_seen_at, which is written
by the session repository on every authenticated request).

Security note:
  All fields are client-reported. The server performs NO fingerprinting
  or behavioural analysis on them. They are stored for audit trails
  and personalisation, not for access control.

Future extension:
  push_notification_token — a device push token (FCM / APNs) to send
  background notifications. Will be added when TASK-5.x implements
  push notifications. Do NOT add it now — adding an unimplemented field
  creates dead columns and a false sense of functionality.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionMetadata:
    """
    Immutable context about the device and locale that initiated a session.

    Attached to AuthenticationSession records for:
      - Audit trail ("logged in from iPhone 14 on iOS 17.1")
      - Personalisation (locale-aware itinerary formatting)
      - Future device trust scoring (trusted device recognition)

    Fields:
        device_id:    Client-generated device identifier (e.g., UUID stored in
                      secure device storage). Optional — not all clients supply it.
        device_name:  Human-readable device label (e.g., "Alice's iPhone 14").
        platform:     Client platform string ("ios", "android", "web").
        app_version:  App version string at the time of login (e.g., "2.1.0").
        locale:       IETF BCP-47 language tag from Accept-Language header
                      (e.g., "en-US", "fr-FR"). Used for i18n.
        timezone:     IANA timezone name from X-Timezone header
                      (e.g., "America/New_York"). Used for tz-aware display.
        last_seen_at: UTC timestamp of the most recent authenticated request.
                      Updated by the session repository on each use.
                      Mutable at the persistence layer — this class is immutable
                      at the domain layer; the repo constructs a fresh instance.
    """

    device_id: str | None = None
    device_name: str | None = None
    platform: str | None = None
    app_version: str | None = None
    locale: str | None = None
    timezone: str | None = None
    last_seen_at: datetime | None = None
    # push_notification_token: str | None = None  — reserved for TASK-5.x

    @classmethod
    def from_login_context(
        cls,
        *,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
        app_version: str | None = None,
        locale: str | None = None,
        timezone: str | None = None,
    ) -> "SessionMetadata":
        """
        Build SessionMetadata from fields available at login time.

        last_seen_at is not set here — it is written by the repository
        the first time the session is actually used post-creation.
        """
        return cls(
            device_id=device_id,
            device_name=device_name,
            platform=platform,
            app_version=app_version,
            locale=locale,
            timezone=timezone,
            last_seen_at=None,
        )

    def with_last_seen(self, last_seen_at: datetime) -> "SessionMetadata":
        """Return a new instance with last_seen_at updated (immutable update)."""
        from dataclasses import replace
        return replace(self, last_seen_at=last_seen_at)
