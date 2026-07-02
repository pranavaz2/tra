"""
Travix AI — Presentation Layer (Shared Kernel)

Shared Pydantic schemas and base classes used in API request/response models
across all feature modules.

This layer may import:
  - Pydantic (v2)
  - app.shared.domain.* (for type references only, not for business logic)

It must NOT import:
  - FastAPI route decorators or router objects
  - SQLAlchemy
  - app.modules.* (no feature module dependencies)
"""
