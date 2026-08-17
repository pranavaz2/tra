"""ItemTitle — validated, stripped itinerary item name."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

_MIN_LENGTH: int = 1
_MAX_LENGTH: int = 100


@dataclass(frozen=True)
class ItemTitle(ValueObject):
    """
    Itinerary item title. 1-100 characters after stripping leading/trailing whitespace.

    Raises:
        ValidationError: if the stripped value is empty or exceeds 100 characters.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        object.__setattr__(self, "value", stripped)

        if len(stripped) < _MIN_LENGTH:
            raise ValidationError(
                "Item title cannot be empty.",
                field="title",
                value=self.value,
            )
        if len(stripped) > _MAX_LENGTH:
            raise ValidationError(
                f"Item title cannot exceed {_MAX_LENGTH} characters "
                f"(got {len(stripped)}).",
                field="title",
                value=self.value,
            )

    def __str__(self) -> str:
        return self.value
