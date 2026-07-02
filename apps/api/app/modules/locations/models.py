"""SQLAlchemy models for the locations module."""

from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.core.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class Geometry(UserDefinedType[object]):
    """Minimal PostGIS geometry column type for SQLAlchemy metadata."""

    cache_ok = True

    def __init__(self, geometry_type: str = "POINT", srid: int = 4326) -> None:
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **kw: object) -> str:
        """Return the PostGIS column specification."""
        return f"geometry({self.geometry_type}, {self.srid})"


class LocationType(str, enum.Enum):
    """Canonical Travix location categories."""

    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    PLACE = "place"
    AIRPORT = "airport"
    LANDMARK = "landmark"


class Location(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Canonical travel location persisted by the locations module."""

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_range"),
        Index("ix_locations_slug", "slug", unique=True),
        Index("ix_locations_country_code", "country_code"),
        Index("ix_locations_type", "location_type"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    point: Mapped[object] = mapped_column(Geometry("POINT", 4326), nullable=False)
    provider_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
