"""RecommendationScore value object."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class RecommendationScore(ValueObject):
    """Recommendation score between 0 and 100."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int):
            try:
                object.__setattr__(self, "value", int(self.value))
            except Exception as exc:
                raise ValidationError(
                    f"Recommendation score must be an integer. Got: {self.value}",
                    field="score",
                    value=self.value,
                ) from exc

        if not 0 <= self.value <= 100:
            raise ValidationError(
                f"Recommendation score must be between 0 and 100. Got: {self.value}",
                field="score",
                value=self.value,
            )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
