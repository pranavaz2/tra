"""SQLAlchemy ORM models for the identity/authentication context."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class UserModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for the users table."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Normalized user email address (lowercase, unique).",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Argon2id password hash.",
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether email has been verified.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Active account flag. Deactivated accounts cannot authenticate.",
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Consecutive failed login counter for brute force lockout.",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Lockout expiry timestamp.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of most recent successful login.",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when password hash was last changed.",
    )

    __mapper_args__ = {"version_id_col": OptimisticLockMixin.version}


class SessionModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """ORM model for the auth_sessions table."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User owning this session.",
    )
    refresh_token_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Active refresh token ID for this session.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Absolute session expiration timestamp.",
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Last activity timestamp on this session.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Explicit revocation timestamp.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address recorded at session creation.",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Client User-Agent header recorded at session creation.",
    )


class RefreshTokenModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """ORM model for the refresh_token_records table."""

    __tablename__ = "refresh_token_records"

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash of the plain refresh token.",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning session ID.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning user ID.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        comment="Token state: active, rotated, expired, revoked.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token expiration timestamp (7 days from issue).",
    )
    rotated_from: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refresh_token_records.id", ondelete="SET NULL"),
        nullable=True,
        comment="Predecessor token in rotation chain.",
    )
    rotated_to: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refresh_token_records.id", ondelete="SET NULL"),
        nullable=True,
        comment="Successor token in rotation chain.",
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when token was rotated.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when token was revoked.",
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for token revocation.",
    )
    device_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Client device identifier.",
    )
    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User-friendly device name.",
    )
    platform: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Client OS/platform.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address from which the token was issued/rotated.",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="User-Agent recorded on issue/rotation.",
    )
    rotation_counter: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Rotation counter for this token in the session sequence.",
    )
