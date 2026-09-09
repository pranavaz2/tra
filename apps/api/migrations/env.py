"""
Alembic Migration Environment

This file is loaded by the Alembic CLI when running any migration command.
It configures the migration context with:
  - The target metadata (all SQLAlchemy model definitions via Base.metadata)
  - The database URL from application settings
  - Migration options (compare_type, compare_server_default)

Database URL strategy:
  Alembic uses a SYNCHRONOUS connection for migrations regardless of whether
  the application uses async SQLAlchemy. We use the DATABASE_SYNC_URL
  (psycopg2 driver) for all migration operations.

Adding new models:
  Import the model module before `target_metadata` is read so that Alembic
  can detect new tables. Add imports in the "Import all models" section below.
  Example:
      from app.modules.trips.models import Trip  # noqa: F401
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import Base so that metadata is available to Alembic
from app.database import Base

# ── Import all models so Alembic can detect schema changes ──────────────────
from app.modules.locations.models import Location  # noqa: F401
from app.modules.identity.authentication.infrastructure.models.auth_models import (  # noqa: F401
    UserModel,
    SessionModel,
    RefreshTokenModel,
)
from app.modules.travel.trips.infrastructure.models.trip_model import TripModel  # noqa: F401
from app.modules.travel.itinerary.infrastructure.models.itinerary_model import (  # noqa: F401
    ItineraryModel,
    ItineraryDayModel,
    ItineraryItemModel,
)
from app.modules.travel.planning.infrastructure.models.proposal_model import TripProposalModel  # noqa: F401
from app.modules.travel.budget.infrastructure.models.budget_model import (  # noqa: F401
    TripBudgetModel,
    BudgetCategoryModel,
    ExpenseModel,
)
from app.modules.travel.sharing.infrastructure.models.sharing_models import (  # noqa: F401
    TripCollaborationModel,
    TripMemberModel,
    InvitationModel,
)
from app.modules.travel.media.infrastructure.models.media_model import (  # noqa: F401
    TripMediaCollectionModel,
    MediaItemModel,
)
from app.modules.travel.recommendations.infrastructure.models.preferences_model import (  # noqa: F401
    UserPreferencesModel,
)
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger("alembic.env")

# Alembic config object — provides access to alembic.ini values
alembic_config = context.config

# Configure Python logging from alembic.ini (applies to CLI runs only)
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# The metadata object that Alembic compares against the live database schema
target_metadata = Base.metadata


def _get_sync_url() -> str:
    """
    Retrieve the synchronous database URL from application settings.

    This is called at migration time (CLI), not at application startup.
    The settings object reads from environment variables or .env.
    """
    from app.config import get_settings

    url = get_settings().database_sync_url.get_secret_value()
    if not url:
        raise RuntimeError(
            "DATABASE_SYNC_URL is not set. "
            "Ensure your .env file or environment defines this variable."
        )
    return url


def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.

    Generates SQL statements to stdout. Useful for reviewing what will be
    applied before touching the database.

    Usage: alembic upgrade head --sql
    """
    url = _get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live database connection.

    Uses NullPool so no connections are held between migration steps.
    This is the standard mode for `alembic upgrade head`.
    """
    url = _get_sync_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            # Render AS constraints in generated SQL
            render_as_batch=False,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
