"""Identity (ADR 0003): anonymous web sessions and keyed Telegram chat lookup."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, User
from unseal.db.session import build_engine, build_session_factory
from unseal.services.identity import (
    chat_hash,
    create_web_user,
    hash_token,
    telegram_user,
    user_for_token,
)

pytestmark = pytest.mark.anyio

CHAT_KEY = SecretStr("test-chat-hash-key")
CHAT_ID = 987654321


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'identity.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield build_session_factory(engine)
    await engine.dispose()


async def test_web_user_gets_a_random_token_and_only_its_hash_is_stored(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        user, token = await create_web_user(session, language="ta")
        other, other_token = await create_web_user(session, language="en")
        await session.commit()
        assert len(token) >= 40 and token != other_token
        assert user.session_token_hash == hash_token(token) != token
        raw = (await session.execute(text("SELECT session_token_hash FROM users"))).scalars().all()
        assert token not in raw and other_token not in raw
        assert user.channel == "web" and user.language == "ta"


async def test_token_lookup_finds_only_the_owner(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        user, token = await create_web_user(session, language="en")
        await session.commit()
        found = await user_for_token(session, token)
        assert found is not None and found.id == user.id
        assert await user_for_token(session, token + "x") is None
        assert await user_for_token(session, "") is None


async def test_telegram_chat_maps_to_one_user_by_keyed_hash(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        first = await telegram_user(session, CHAT_ID, key=CHAT_KEY, language="ta")
        await session.commit()
        again = await telegram_user(session, CHAT_ID, key=CHAT_KEY, language="en")
        await session.commit()
        assert again.id == first.id and again.language == "ta"  # existing user, unchanged
        assert first.telegram_chat_id == str(CHAT_ID)  # decrypted for sending
        raw = (await session.execute(text("SELECT telegram_chat_id FROM users"))).scalar_one()
        assert str(CHAT_ID) not in raw  # stored encrypted
        assert (await session.execute(select(User))).scalars().all() == [first]


def test_chat_hash_is_keyed_and_stable() -> None:
    assert chat_hash(CHAT_ID, CHAT_KEY) == chat_hash(str(CHAT_ID), CHAT_KEY)
    assert chat_hash(CHAT_ID, CHAT_KEY) != chat_hash(CHAT_ID, SecretStr("another-key"))
    assert len(chat_hash(CHAT_ID, CHAT_KEY)) == 64
