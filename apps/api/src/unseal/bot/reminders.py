"""FR-9 on Telegram: send a reminder the scheduler has claimed (`scheduler.tick`).

The text names only the deadline and its date, in the user's language; the chat id is decrypted
here to send and is never logged. A user without a Telegram chat (a web user) is skipped.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Bot

from unseal.bot.finish import shown_date
from unseal.bot.logs import quiet_library_logs
from unseal.bot.texts import Language, label, language_of, t
from unseal.db.models import Case, Deadline, User
from unseal.scheduler import REMINDER_WINDOWS, Reminder, Send

log = logging.getLogger("unseal.bot")


def reminder_text(reminder: Reminder, language: Language, *, estimated: bool) -> str:
    days = REMINDER_WINDOWS[reminder.window]
    key = {0: "reminder_today", 1: "reminder_tomorrow"}.get(days, "reminder_ahead")
    kind = label("kind", reminder.kind, language)
    when = shown_date(reminder.due_on, estimated, language)
    first = t(key, language, kind=kind, date=when, days=days)
    return first + "\n" + t("reminder_more", language)


def reminder_sender(bot: Bot, factory: async_sessionmaker[AsyncSession]) -> Send:
    quiet_library_logs()

    async def send(reminder: Reminder) -> None:
        async with factory() as session:
            case = await session.get(Case, reminder.case_id)
            user = await session.get(User, case.user_id) if case else None
            deadline = await session.get(Deadline, reminder.deadline_id)
        if case is None or user is None or deadline is None:
            log.info("reminder %s for deadline %s skipped: case gone", *_ids(reminder))
            return
        if user.telegram_chat_id is None:
            log.info("reminder %s for deadline %s skipped: no Telegram chat", *_ids(reminder))
            return
        language = language_of(user.language)
        text = reminder_text(reminder, language, estimated=deadline.estimated)
        await bot.send_message(int(user.telegram_chat_id), text)
        log.info("reminder %s for deadline %s sent on Telegram", *_ids(reminder))

    return send


def _ids(reminder: Reminder) -> tuple[str, str]:
    return reminder.window, reminder.deadline_id
