"""Money value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class Money(ValueObject):
    """Represent an amount of money in a specific currency."""

    amount: Decimal
    currency: CurrencyCode

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            # Try parsing to Decimal
            try:
                object.__setattr__(self, "amount", Decimal(str(self.amount)))
            except Exception as exc:
                raise ValidationError(
                    f"Amount must be a valid decimal number. Got: {self.amount}",
                    field="amount",
                    value=self.amount,
                ) from exc

        # Quantize to 2 decimal places
        object.__setattr__(self, "amount", self.amount.quantize(Decimal("0.01")))

    def is_zero(self) -> bool:
        return self.amount == Decimal("0.00")

    def is_positive(self) -> bool:
        return self.amount > Decimal("0.00")

    def is_negative(self) -> bool:
        return self.amount < Decimal("0.00")

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValidationError(
                f"Cannot add money of different currencies: {self.currency} and {other.currency}."
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValidationError(
                f"Cannot subtract money of different currencies: "
                f"{self.currency} and {other.currency}."
            )
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
