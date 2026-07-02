"""
Travix AI — Value Object

A Value Object is defined entirely by its ATTRIBUTES. Two value objects
with the same attributes are identical. Value objects are IMMUTABLE — once
created, their state cannot change.

Design:
  - Frozen dataclass: Python raises FrozenInstanceError on mutation attempts.
  - Equality by attribute values (dataclass default for frozen classes).
  - No identity field (no entity_id, no created_at).
  - Validation in __post_init__; raise ValidationError for invalid state.

Usage — defining a value object:
    from dataclasses import dataclass
    from app.shared.domain.value_object import ValueObject
    from app.shared.domain.errors import ValidationError

    @dataclass(frozen=True)
    class EmailAddress(ValueObject):
        value: str

        def __post_init__(self) -> None:
            if "@" not in self.value:
                raise ValidationError("Invalid email address.", field="email")

    email = EmailAddress("user@example.com")
    email.value = "other@example.com"  # raises FrozenInstanceError

Usage — using a value object inside an entity:
    @dataclass(kw_only=True, eq=False)
    class User(AggregateRoot[UUID]):
        email: EmailAddress
        ...

Value objects are not persisted directly — they are mapped to columns
inside the module's SQLAlchemy model using composite columns or JSON.

Note: Subclasses must apply @dataclass(frozen=True) themselves. Python
dataclass inheritance requires each class to declare its own @dataclass
decorator with the desired parameters.
"""

from __future__ import annotations


class ValueObject:
    """
    Marker base class for all value objects.

    Apply @dataclass(frozen=True) to every subclass:

        @dataclass(frozen=True)
        class Money(ValueObject):
            amount: Decimal
            currency: str

    Equality is automatically handled by the frozen dataclass decorator.
    """

    __slots__ = ()
