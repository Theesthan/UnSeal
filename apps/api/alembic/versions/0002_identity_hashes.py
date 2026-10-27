"""identity hashes

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27

ADR 0003: users.session_token_hash (SHA-256 of the web session token) and
users.telegram_chat_hash (HMAC of the Telegram chat id), both nullable with unique indexes.
Questions now hold Fernet tokens for original_text and rewritten_text; the column type stays
TEXT, so no DDL is needed for that (there is no production data to re-encrypt yet).

Additive only. Downgrade drops the two new indexes and columns, which hold only hashes.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("session_token_hash", "telegram_chat_hash")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("users", sa.Column(column, sa.String(length=64), nullable=True))
        op.create_index(op.f(f"ix_users_{column}"), "users", [column], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in _COLUMNS:
            batch.drop_index(op.f(f"ix_users_{column}"))
            batch.drop_column(column)
