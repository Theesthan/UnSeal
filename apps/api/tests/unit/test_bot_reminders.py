"""FR-9 on Telegram: a reminder the scheduler claimed reaches the user's chat, in their language,
with the deadline kind and date and no personal data; the chat id is never logged."""

import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Bot
from test_bot_fakes import (
    ADDRESS,
    BOT_TOKEN,
    CHAT_ID,
    NAME,
    FakeRequest,
    bot_settings,
    dispose,
    filed_case,
    make_db,
    reminder_for,
    use_test_key,
)

from unseal.bot.reminders import reminder_sender
from unseal.bot.texts import format_date, t
from unseal.db.models import Case

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _test_key() -> Iterator[None]:
    yield from use_test_key()


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    made = await make_db(bot_settings(tmp_path))
    yield made
    await dispose(made)


@pytest.fixture
async def bot() -> AsyncIterator[tuple[Bot, FakeRequest]]:
    request = FakeRequest()
    telegram_bot = Bot(BOT_TOKEN, request=request, get_updates_request=FakeRequest())
    await telegram_bot.initialize()
    yield telegram_bot, request
    await telegram_bot.shutdown()


@pytest.mark.parametrize(
    ("window", "key", "values"),
    [
        ("7d", "reminder_ahead", {"days": 7}),
        ("1d", "reminder_tomorrow", {}),
        ("due", "reminder_today", {}),
    ],
)
async def test_a_reminder_reaches_the_chat_in_the_user_language(
    factory: async_sessionmaker[AsyncSession],
    bot: tuple[Bot, FakeRequest],
    caplog: pytest.LogCaptureFixture,
    window: str,
    key: str,
    values: dict[str, int],
) -> None:
    telegram_bot, request = bot
    case = await filed_case(factory, telegram=True)
    reminder = reminder_for(case, "pio_reply", window)
    with caplog.at_level(logging.DEBUG):
        await reminder_sender(telegram_bot, factory)(reminder)
    [sent] = request.sent("sendMessage")
    assert sent.params["chat_id"] == CHAT_ID
    due = format_date(reminder.due_on, "ta") + " " + t("estimated", "ta")  # receipt estimated
    kind = t("kind_pio_reply", "ta")
    assert sent.params["text"] == t(key, "ta", kind=kind, date=due, **values) + "\n" + t(
        "reminder_more", "ta"
    )
    assert NAME not in sent.params["text"] and ADDRESS not in sent.params["text"]
    assert str(CHAT_ID) not in caplog.text


async def test_a_web_user_is_skipped_and_logged(
    factory: async_sessionmaker[AsyncSession],
    bot: tuple[Bot, FakeRequest],
    caplog: pytest.LogCaptureFixture,
) -> None:
    telegram_bot, request = bot
    case = await filed_case(factory, telegram=False, language="en")
    with caplog.at_level(logging.INFO):
        await reminder_sender(telegram_bot, factory)(reminder_for(case, "first_appeal", "1d"))
    assert request.sent("sendMessage") == []
    assert "no Telegram chat" in caplog.text


async def test_a_deleted_case_is_skipped(
    factory: async_sessionmaker[AsyncSession],
    bot: tuple[Bot, FakeRequest],
    caplog: pytest.LogCaptureFixture,
) -> None:
    telegram_bot, request = bot
    case = await filed_case(factory, telegram=True)
    reminder = reminder_for(case, "pio_reply", "due")
    async with factory() as session:
        await session.delete(await session.get(Case, case.id))
        await session.commit()
    with caplog.at_level(logging.INFO):
        await reminder_sender(telegram_bot, factory)(reminder)
    assert request.sent("sendMessage") == []
    assert "skipped" in caplog.text and str(CHAT_ID) not in caplog.text
