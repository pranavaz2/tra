"""RecommendationReason value object."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class RecommendationReason(ValueObject):
    """Reason for a recommendation."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError(
                "Recommendation reason is required and cannot be empty.", field="reason"
            )

        object.__setattr__(self, "value", self.value.strip())

    def __str__(self) -> str:
        return self.value
