"""InterestTag value object."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class InterestTag(ValueObject):
    """Interest tag representing a travel interest."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("Interest tag cannot be empty.", field="interests")

        # Normalize: strip whitespace and lowercase
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
