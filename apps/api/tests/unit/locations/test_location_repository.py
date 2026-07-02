"""Unit tests for location repository query construction."""

from __future__ import annotations

from app.modules.locations.models import LocationType
from app.modules.locations.repository import LocationRepository


def _sql(statement: object) -> str:
    """Compile a SQLAlchemy statement to a readable SQL string."""
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def test_base_search_excludes_soft_deleted_rows() -> None:
    repo = LocationRepository(session=None)  # type: ignore[arg-type]

    stmt = repo._base_search_query(query=None, country_code=None, location_type=None)

    assert "deleted_at IS NULL" in _sql(stmt)


def test_base_search_filters_by_country_code() -> None:
    repo = LocationRepository(session=None)  # type: ignore[arg-type]

    stmt = repo._base_search_query(query=None, country_code="fr", location_type=None)

    assert "locations.country_code = 'FR'" in _sql(stmt)


def test_base_search_filters_by_location_type() -> None:
    repo = LocationRepository(session=None)  # type: ignore[arg-type]

    stmt = repo._base_search_query(query=None, country_code=None, location_type=LocationType.CITY)

    assert "locations.location_type = 'city'" in _sql(stmt)


def test_base_search_filters_by_name_region_or_locality() -> None:
    repo = LocationRepository(session=None)  # type: ignore[arg-type]

    stmt = repo._base_search_query(query="paris", country_code=None, location_type=None)
    sql = _sql(stmt).lower()

    assert "locations.name" in sql
    assert "locations.region" in sql
    assert "locations.locality" in sql
    assert "%paris%" in sql
