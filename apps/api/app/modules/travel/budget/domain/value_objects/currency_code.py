"""CurrencyCode value object."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class CurrencyCode(ValueObject):
    """3-letter ISO 4217 Currency Code value object."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) != 3 or not self.value.isalpha():
            raise ValidationError(
                "Currency code must be a 3-letter alphabetic string.",
                field="currency",
                value=self.value,
            )
        # Normalize to uppercase
        object.__setattr__(self, "value", self.value.upper())

    def __str__(self) -> str:
        return self.value
