"""
Travix AI — Application Layer (Shared Kernel)

Application-level abstractions used by all feature modules.

The application layer may import from:
  - app.shared.domain.*       (domain abstractions)
  - app.shared.infrastructure.* (infrastructure interfaces)

It must NOT import from:
  - FastAPI
  - SQLAlchemy
  - Any external provider package

The single export from this layer is ApplicationContext — the container
for infrastructure dependencies needed by use cases and background workers.
"""
