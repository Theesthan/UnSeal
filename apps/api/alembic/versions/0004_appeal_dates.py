"""appeal dates

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27

FR-10 needs two dates on a case:
- cases.reply_received_on: the day the PIO's reply arrived (the first appeal cites it, and the
  S. 19(1) window runs from it)
- cases.appeal_filed_on: the day the first appeal was filed (the FAA's S. 19(6) clock)

Additive and nullable, so every existing row stays valid. Downgrade, like 0001, only runs on an
empty database. SQLite cannot drop a column in place, so the downgrade goes through batch mode.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("reply_received_on", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("appeal_filed_on", sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM cases LIMIT 1")).first() is not None:
        raise RuntimeError(
            "Refusing to downgrade 0004: table 'cases' holds data. Dropping these columns would "
            "lose case dates; export or delete the rows first."
        )
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("appeal_filed_on")
        batch.drop_column("reply_received_on")
