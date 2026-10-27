"""Telegram account lookups and deletion (ADR 0003, FR-8)."""

from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unseal.db.models import Case, Document, User
from unseal.services.identity import chat_hash
from unseal.services.storage import remove_files


async def find_user(session: AsyncSession, chat_id: int, key: SecretStr) -> User | None:
    """The user for this chat, or None. Never creates one: nothing is stored before consent."""
    lookup = chat_hash(chat_id, key)
    found = await session.execute(select(User).where(User.telegram_chat_hash == lookup))
    return found.scalar_one_or_none()


async def delete_user(session: AsyncSession, user: User, storage_dir: Path) -> None:
    """FR-8, the same steps as `DELETE /me` (api/session.py): every row by cascade, then every
    stored file. ponytail: duplicated from the route because that logic is inline there; move
    both to one services helper when someone next touches api/session.py."""
    keys = select(Document.storage_key).join(Case).where(Case.user_id == user.id)
    storage_keys = list((await session.execute(keys)).scalars())
    await session.delete(user)
    await session.commit()
    remove_files(storage_dir, storage_keys)
