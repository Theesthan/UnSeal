"""Helpers shared by the bot handlers: conversation states, per-update services, replies and the
model-call guard. Handlers never log message text, names or addresses (CLAUDE.md, privacy)."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from enum import IntEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from unseal.bot.account import find_user
from unseal.bot.services import BotServices, ChatQuota
from unseal.bot.texts import Language, language_of, t
from unseal.db.models import Case, User
from unseal.llm.client import ModelBusy, ModelIncomplete, ModelOutputInvalid
from unseal.services.cases import NotFound, get_case

log = logging.getLogger("unseal.bot")

Ctx = ContextTypes.DEFAULT_TYPE

MAX_MESSAGE = 4000  # Telegram's limit is 4096 characters
MAX_BUTTON = 60
# Input caps: they bound what reaches the model (the daily token cap is shared by everyone).
MAX_DESCRIPTION = 2000
MAX_QUESTION = 1000
MAX_ANSWER = 500
MAX_NAME = 200
MAX_ADDRESS = 500
MAX_PLACE = 100


class S(IntEnum):
    """Conversation states. ponytail: ConversationHandler keeps them in memory, so a restart
    loses every chat's place in the flow (cases already saved stay in the database)."""

    LANGUAGE = 1
    CONSENT = 2
    DESCRIBE = 3
    FOLLOW_UP = 4
    AUTHORITY = 5
    AUTHORITY_NAME = 6
    AUTHORITY_ADDRESS = 7
    JURISDICTION = 8
    CONFIRM = 9
    REVIEW = 10
    EDIT = 11
    NEW_QUESTION = 12
    NAME = 13
    ADDRESS = 14
    BPL = 15
    PAYMENT = 16
    PLACE = 17
    FILED_DATE = 18
    FILED_MODE = 19


def services(context: Ctx) -> BotServices:
    found = context.bot_data["services"]
    assert isinstance(found, BotServices)
    return found


def quota(context: Ctx) -> ChatQuota:
    found = context.bot_data["quota"]
    assert isinstance(found, ChatQuota)
    return found


def data(context: Ctx) -> dict[str, Any]:
    """This chat's in-memory flow state (never written to disk, never logged)."""
    store = context.user_data
    assert store is not None
    return store


def lang(context: Ctx) -> Language:
    return language_of(data(context).get("lang"))


def chat_id(update: Update) -> int:
    chat = update.effective_chat
    assert chat is not None
    return chat.id


def clip(text: str, limit: int = MAX_MESSAGE) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def keyboard(rows: Sequence[Sequence[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Buttons from (label, callback_data) rows. callback_data is a fixed code or an opaque id,
    never personal data."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(clip(label, MAX_BUTTON), callback_data=code)
                for label, code in row
            ]
            for row in rows
        ]
    )


def button(context: Ctx, key: str, code: str) -> tuple[str, str]:
    return t(key, lang(context)), code


async def send(
    update: Update, context: Ctx, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    """Plain text, no parse mode: model text with `<` or `*` is shown as typed."""
    await context.bot.send_message(chat_id(update), clip(text), reply_markup=markup)


async def say(
    update: Update,
    context: Ctx,
    key: str,
    markup: InlineKeyboardMarkup | None = None,
    **values: object,
) -> None:
    await send(update, context, t(key, lang(context), **values), markup)


async def tapped(update: Update) -> str:
    """Acknowledge a button press and return its callback data."""
    query = update.callback_query
    assert query is not None
    await query.answer()
    return query.data or ""


async def take_text(update: Update, context: Ctx, limit: int) -> str | None:
    """The message text, or None after telling the user it is empty or too long."""
    message = update.effective_message
    text = (message.text if message else None) or ""
    text = text.strip()
    if not text:
        await say(update, context, "empty")
        return None
    if len(text) > limit:
        await say(update, context, "too_long", limit=limit)
        return None
    return text


async def current_user(session: AsyncSession, update: Update, context: Ctx) -> User | None:
    key = services(context).settings.telegram_chat_hash_key
    assert key is not None  # the bot does not start without it
    return await find_user(session, chat_id(update), key)


async def load_case(session: AsyncSession, update: Update, context: Ctx) -> Case:
    """This chat's current case, with questions, deadlines and applicant. NotFound if the user or
    the case is gone (for example after /delete)."""
    user = await current_user(session, update, context)
    case_id = data(context).get("case_id")
    if user is None or not isinstance(case_id, str):
        raise NotFound
    return await get_case(session, user, case_id)


def clear_flow(context: Ctx) -> None:
    """Forget the in-memory flow, keeping only the chosen language."""
    store = data(context)
    language = store.get("lang")
    store.clear()
    if language:
        store["lang"] = language


Action = Callable[[], Awaitable[int]]


async def guarded(
    update: Update,
    context: Ctx,
    *,
    pending: dict[str, str],
    stay: S,
    invalid_key: str,
    action: Action,
) -> int:
    """Run a model-backed step. Busy or cut-off answers offer a Retry (the step is kept in memory
    as `pending`); an unusable answer asks the user to rephrase; the state stays put."""
    store = data(context)
    if not quota(context).allow(chat_id(update)):
        await say(update, context, "rate_limited")
        return stay
    await say(update, context, "working")
    retry = keyboard([[button(context, "retry", "retry")]])
    try:
        next_state = await action()
    except ModelBusy:
        log.info("telegram step %s: model busy", pending["kind"])
        store["pending"] = pending
        await say(update, context, "busy", retry)
        return stay
    except ModelIncomplete:
        log.info("telegram step %s: model output incomplete", pending["kind"])
        store["pending"] = pending
        await say(update, context, "incomplete", retry)
        return stay
    except ModelOutputInvalid:
        log.info("telegram step %s: model output unusable", pending["kind"])
        store.pop("pending", None)
        await say(update, context, invalid_key)
        return stay
    store.pop("pending", None)
    return next_state
