"""initial

Revision ID: 0001
Revises:
Create Date: 2026-10-27

Creates users, applicants, cases, questions, deadlines and documents.

Applicant name, address and phone, and users.telegram_chat_id, hold Fernet tokens (see
unseal/db/crypto.py), so they are plain TEXT here. Foreign keys cascade on delete: removing a user
removes everything they own, and removing a case removes its questions, deadlines and documents.

Migrations here are additive and reviewable. Never DROP a table or column that holds data, and
never import application code: spell types as plain `sa.*` so this file keeps working as the
models change.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Children first, so that dropping in this order never trips a foreign key.
_TABLES_CHILDREN_FIRST = ("questions", "deadlines", "documents", "cases", "applicants", "users")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("telegram_chat_id", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("channel IN ('web', 'telegram')", name=op.f("ck_users_channel")),
        sa.CheckConstraint("language IN ('en', 'hi', 'ta')", name=op.f("ck_users_language")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    op.create_table(
        "applicants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_applicants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applicants")),
    )
    op.create_index(op.f("ix_applicants_user_id"), "applicants", ["user_id"], unique=False)

    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("applicant_id", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("authority_name", sa.Text(), nullable=True),
        sa.Column("pio_address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("via_apio", sa.Boolean(), nullable=False),
        sa.Column("third_party", sa.Boolean(), nullable=False),
        sa.Column("life_liberty", sa.Boolean(), nullable=False),
        sa.Column("filing_mode", sa.String(length=32), nullable=True),
        sa.Column("filed_on", sa.Date(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("transferred_to", sa.Text(), nullable=True),
        sa.Column("transfer_received_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("language IN ('en', 'hi', 'ta')", name=op.f("ck_cases_language")),
        sa.CheckConstraint(
            "status IN ('draft', 'filed', 'reply_due', 'replied', 'deemed_refused', "
            "'appealed', 'closed')",
            name=op.f("ck_cases_status"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_cases_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_cases_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
    )
    op.create_index(op.f("ix_cases_user_id"), "cases", ["user_id"], unique=False)
    op.create_index(op.f("ix_cases_applicant_id"), "cases", ["applicant_id"], unique=False)
    # The 180-day retention job selects closed cases by age.
    op.create_index("ix_cases_status_closed_on", "cases", ["status", "closed_on"], unique=False)

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_questions_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_index(op.f("ix_questions_case_id"), "questions", ["case_id"], unique=False)

    op.create_table(
        "deadlines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("reminded_7d_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminded_1d_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminded_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('pio_reply', 'first_appeal', 'faa_decision', 'second_appeal')",
            name=op.f("ck_deadlines_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_deadlines_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deadlines")),
        sa.UniqueConstraint("case_id", "kind", name=op.f("uq_deadlines_case_id_kind")),
    )
    op.create_index("ix_deadlines_due_on", "deadlines", ["due_on"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('application', 'first_appeal', 'second_appeal', 'reply_image')",
            name=op.f("ck_documents_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_documents_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
    )
    op.create_index(op.f("ix_documents_case_id"), "documents", ["case_id"], unique=False)


def downgrade() -> None:
    # Dropping tables destroys personal data, so only an empty database may be downgraded.
    bind = op.get_bind()
    for table in _TABLES_CHILDREN_FIRST:
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None:
            raise RuntimeError(
                f"Refusing to downgrade 0001: table {table!r} holds data. Dropping it would "
                "delete personal data; export or delete the rows deliberately first."
            )
    for table in _TABLES_CHILDREN_FIRST:
        op.drop_table(table)
