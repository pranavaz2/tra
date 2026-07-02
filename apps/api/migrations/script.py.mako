"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Migration checklist (delete this block before merging):
  [ ] Reviewed auto-generated DDL for correctness
  [ ] Added GiST index for every PostGIS geometry column
  [ ] Added updated_at trigger for every new table
  [ ] Added soft-delete column (deleted_at) for user-facing entities
  [ ] Verified ON DELETE behaviour on all foreign keys
  [ ] Tested upgrade AND downgrade locally
  [ ] downgrade() fully reverses upgrade() with no data loss (where possible)
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Revision identifiers — used by Alembic to order migrations
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
