"""
Email value object.

Normalises and validates email addresses at construction time.
The normalised form (lowercase, stripped) is the canonical representation
used throughout the domain — two Email objects with the same normalised
address compare equal regardless of the original casing.

Exports:
  Email                 — the value object
  is_valid_email_format — pure function used by ValidEmailSpecification
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.identity.authentication.domain.errors import InvalidEmailError
from app.shared.domain.value_object import ValueObject

# RFC 5321 / RFC 5322 practical subset — covers real-world email addresses.
# Deliberately not exhaustive: overly strict regexes reject valid addresses.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9]"                    # local part must start with alnum
    r"[a-zA-Z0-9._%+\-]*"              # local part body
    r"@"
    r"[a-zA-Z0-9]"                      # domain must start with alnum
    r"[a-zA-Z0-9.\-]*"                  # domain body
    r"\.[a-zA-Z]{2,}$"                  # TLD: at least two alpha chars
)


def is_valid_email_format(value: str) -> bool:
    """Return True if value matches a practical email pattern."""
    return bool(_EMAIL_RE.match(value.strip()))


@dataclass(frozen=True)
class Email(ValueObject):
    """
    A normalised, validated email address.

    Invariants:
      - Whitespace stripped, lowercased on construction.
      - Matches a practical email regex (see _EMAIL_RE).

    Raises:
      InvalidEmailError: if the normalised value fails format validation.
    """

    value: str

    def __post_init__(self) -> None:
        # Normalise before validation; frozen=True requires object.__setattr__.
        normalised = self.value.strip().lower()
        object.__setattr__(self, "value", normalised)

        if not is_valid_email_format(normalised):
            raise InvalidEmailError(f"'{normalised}' is not a valid email address.")

    def __str__(self) -> str:
        return self.value
