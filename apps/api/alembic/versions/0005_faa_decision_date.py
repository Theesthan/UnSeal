"""faa decision date

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27

FR-12: cases.faa_decision_received_on, the day the appellate authority's order arrived. The
second-appeal window (S. 19(3)) runs from it; without it the stored deadline would be anchored
on the order's due date, which is later than the real one when the order comes early.

Additive and nullable. Downgrade, like 0001, only runs on an empty database.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("faa_decision_received_on", sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM cases LIMIT 1")).first() is not None:
        raise RuntimeError(
            "Refusing to downgrade 0005: table 'cases' holds data. Dropping this column would "
            "lose case dates; export or delete the rows first."
        )
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("faa_decision_received_on")
