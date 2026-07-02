"""
Authentication bounded context.

Layers (inner → outer):
  domain/          Pure domain model — no framework imports.
  application/     Use cases and application services.
  infrastructure/  SQLAlchemy models, JWT, bcrypt, Redis adapters.
  api/             FastAPI routes and Pydantic schemas.
"""
