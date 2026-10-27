"""Anonymous identity (ADR 0003).

Web: a random session token lives only in the user's HttpOnly cookie; the database keeps its
SHA-256. Telegram: a chat is found by HMAC-SHA256 of its id under TELEGRAM_CHAT_HASH_KEY, and the
id itself is stored Fernet-encrypted so the bot can message the user.
"""

import hashlib
import hmac
import secrets
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unseal.db.models import Case, Channel, Document, User
from unseal.services.storage import remove_files

TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def chat_hash(chat_id: int | str, key: SecretStr) -> str:
    digest = hmac.new(key.get_secret_value().encode(), str(chat_id).encode(), hashlib.sha256)
    return digest.hexdigest()


async def create_web_user(session: AsyncSession, *, language: str) -> tuple[User, str]:
    """A new anonymous web user and the token for its cookie (returned once, never stored)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    user = User(channel=Channel.WEB.value, language=language, session_token_hash=hash_token(token))
    session.add(user)
    await session.flush()
    return user, token


async def user_for_token(session: AsyncSession, token: str) -> User | None:
    if not token:
        return None
    found = await session.execute(select(User).where(User.session_token_hash == hash_token(token)))
    return found.scalar_one_or_none()


async def telegram_user(
    session: AsyncSession, chat_id: int, *, key: SecretStr, language: str
) -> User:
    """The user for this Telegram chat, created on first contact."""
    lookup = chat_hash(chat_id, key)
    found = await session.execute(select(User).where(User.telegram_chat_hash == lookup))
    user = found.scalar_one_or_none()
    if user is None:
        user = User(
            channel=Channel.TELEGRAM.value,
            language=language,
            telegram_chat_id=str(chat_id),
            telegram_chat_hash=lookup,
        )
        session.add(user)
        await session.flush()
    return user


async def find_telegram_user(session: AsyncSession, chat_id: int, key: SecretStr) -> User | None:
    """The user for this chat, or None. Never creates one: nothing is stored before consent."""
    lookup = chat_hash(chat_id, key)
    found = await session.execute(select(User).where(User.telegram_chat_hash == lookup))
    return found.scalar_one_or_none()


async def delete_user(session: AsyncSession, user: User, storage_dir: Path) -> None:
    """FR-8, for DELETE /me and the bot's /delete alike: every row by cascade, then every
    stored file."""
    keys = select(Document.storage_key).join(Case).where(Case.user_id == user.id)
    storage_keys = list((await session.execute(keys)).scalars())
    await session.delete(user)
    await session.commit()
    remove_files(storage_dir, storage_keys)
