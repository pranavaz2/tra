"""
Travix AI — Database Infrastructure Package

Cross-cutting persistence infrastructure used by all feature modules.

Public API:
  app.core.db.mixins        → ORM column mixins (UUID PK, timestamps, soft-delete, locking)
  app.core.db.repository    → Generic SQLAlchemyRepository base
  app.core.db.unit_of_work  → UnitOfWork Protocol + SQLAlchemyUnitOfWork
  app.core.db.query         → Sort, filter, spec-to-clause, cursor pagination helpers
  app.core.db.events        → SQLAlchemy engine event hooks (query timing, slow query log)

Import discipline:
  - These modules import from sqlalchemy.* and app.config only.
  - They do NOT import from any feature module (app.modules.*).
  - app.database imports from this package, not the other way around.
"""
