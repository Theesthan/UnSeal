"""case details

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27

Columns the case routes need (docs/api.md):
- applicants.bpl (S. 7(5) fee exemption)
- cases.applicant_id becomes nullable (a draft exists before the applicant's details) and
  cases.received_estimated records an engine-estimated receipt date
- questions.details (Fernet token of the rewrite's records, reason and suggestion) and
  questions.personal_information (the rewrite step's flag)

Additive: new columns have server defaults, and relaxing NOT NULL keeps every existing row.
Downgrade, like 0001, only runs on an empty database.
SQLite cannot alter a column in place, so the cases change goes through batch mode.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applicants", sa.Column("bpl", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("questions", sa.Column("details", sa.Text(), nullable=True))
    op.add_column(
        "questions",
        sa.Column("personal_information", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    with op.batch_alter_table("cases") as batch:
        batch.alter_column("applicant_id", existing_type=sa.String(length=36), nullable=True)
        batch.add_column(
            sa.Column("received_estimated", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    # Like 0001: only an empty database may lose these columns (questions.details is user data).
    bind = op.get_bind()
    for table in ("questions", "cases", "applicants"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None:
            raise RuntimeError(
                f"Refusing to downgrade 0003: table {table!r} holds data. Dropping these "
                "columns would delete personal data; export or delete the rows first."
            )
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("received_estimated")
        batch.alter_column("applicant_id", existing_type=sa.String(length=36), nullable=False)
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("personal_information")
        batch.drop_column("details")
    with op.batch_alter_table("applicants") as batch:
        batch.drop_column("bpl")
