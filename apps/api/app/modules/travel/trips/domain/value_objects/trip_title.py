"""TripTitle — validated, stripped trip name."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

_MIN_LENGTH: int = 1
_MAX_LENGTH: int = 100


@dataclass(frozen=True)
class TripTitle(ValueObject):
    """
    Trip name. 1–100 characters after stripping leading/trailing whitespace.

    Normalised to stripped form on construction. Two titles with the same
    stripped text compare equal.

    Raises:
        ValidationError: if the stripped value is empty or exceeds 100 characters.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        object.__setattr__(self, "value", stripped)

        if len(stripped) < _MIN_LENGTH:
            raise ValidationError(
                "Trip title cannot be empty.",
                field="title",
                value=self.value,
            )
        if len(stripped) > _MAX_LENGTH:
            raise ValidationError(
                f"Trip title cannot exceed {_MAX_LENGTH} characters "
                f"(got {len(stripped)}).",
                field="title",
                value=self.value,
            )

    def __str__(self) -> str:
        return self.value
