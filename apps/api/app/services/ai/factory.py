"""
AI provider factory — selects the concrete PlanningEngine implementation.

Reads the AI_PROVIDER setting and returns the matching implementation.
Currently only the MockPlanningEngine is available.

When a real provider is implemented:
  1. Create app/services/ai/{provider_name}.py with a class implementing PlanningEngine.
  2. Add a branch to get_planning_engine() keyed on the AI_PROVIDER config value.
  3. The feature module code changes zero lines — only the factory changes.

See CLAUDE.md §12 for the service abstraction pattern.
"""

from __future__ import annotations

from app.services.ai.base import PlanningEngine
from app.services.ai.mock import MockPlanningEngine


def get_planning_engine() -> PlanningEngine:
    """
    Return the active PlanningEngine implementation.

    Currently returns MockPlanningEngine unconditionally. When a real
    provider is configured, this function will read the AI_PROVIDER
    setting and select the appropriate implementation.
    """
    return MockPlanningEngine()
