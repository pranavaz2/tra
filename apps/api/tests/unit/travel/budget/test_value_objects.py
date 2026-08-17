"""Unit tests for Budget domain Value Objects."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.shared.domain.errors import ValidationError


def test_budget_identifiers() -> None:
    """Test UUID identifiers validation and generation."""
    b_id = BudgetId.generate()
    assert isinstance(b_id.value, UUID)
    assert len(str(b_id)) == 36

    c_id = CategoryId.generate()
    assert isinstance(c_id.value, UUID)

    e_id = ExpenseId.generate()
    assert isinstance(e_id.value, UUID)

    parsed = BudgetId.from_str(str(b_id))
    assert parsed == b_id


def test_currency_code_validation() -> None:
    """Test ISO 4217 currency code validation and normalization."""
    code = CurrencyCode("usd")
    assert code.value == "USD"
    assert str(code) == "USD"

    with pytest.raises(ValidationError):
        CurrencyCode("US")

    with pytest.raises(ValidationError):
        CurrencyCode("USD1")

    with pytest.raises(ValidationError):
        CurrencyCode("")


def test_money_arithmetic_and_validation() -> None:
    """Test Money creation, rounding, and operations."""
    m1 = Money(amount=Decimal("100.554"), currency=CurrencyCode("EUR"))
    assert m1.amount == Decimal("100.55")

    m2 = Money(amount=Decimal("50.25"), currency=CurrencyCode("EUR"))
    m3 = m1.add(m2)
    assert m3.amount == Decimal("150.80")
    assert str(m3) == "150.80 EUR"

    m4 = m1.subtract(m2)
    assert m4.amount == Decimal("50.30")

    # Mismatched currency
    m_usd = Money(amount=Decimal("10"), currency=CurrencyCode("USD"))
    with pytest.raises(ValidationError):
        m1.add(m_usd)

    with pytest.raises(ValidationError):
        m1.subtract(m_usd)

    assert m1.is_positive()
    assert not m1.is_negative()
    assert not m1.is_zero()

    zero_money = Money(amount=Decimal("0.00"), currency=CurrencyCode("USD"))
    assert zero_money.is_zero()
