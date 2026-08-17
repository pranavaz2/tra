"""TravelStyle enum."""

from __future__ import annotations

from enum import StrEnum


class TravelStyle(StrEnum):
    """Supported styles of travel preferences."""

    ADVENTURE = "adventure"
    CULTURE = "culture"
    RELAXATION = "relaxation"
    FOOD = "food"
    NATURE = "nature"
    SHOPPING = "shopping"
    FAMILY = "family"
