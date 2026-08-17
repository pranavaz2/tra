"""
Travix AI — AI Service Abstraction Layer

Provides the PlanningEngine interface and its implementations.
Feature modules import only from this package — never from provider SDKs.

See CLAUDE.md §4.6, §4.7, §12 for the abstraction rules.
"""

from app.services.ai.base import PlanningEngine
from app.services.ai.mock import MockPlanningEngine

__all__ = ["MockPlanningEngine", "PlanningEngine"]
