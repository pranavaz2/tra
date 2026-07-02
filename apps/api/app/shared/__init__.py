"""
Travix AI — Shared Kernel

Domain-level building blocks shared across all feature modules.

Import discipline:
  - app.shared.domain.*       → pure Python, no framework imports
  - app.shared.infrastructure.* → stdlib only, no SQLAlchemy, no Redis
  - app.shared.application.*  → may import from domain and infrastructure
  - app.shared.presentation.* → may import Pydantic, domain schemas

Feature modules (app.modules.*) import FROM the shared kernel.
The shared kernel NEVER imports FROM feature modules.
"""
