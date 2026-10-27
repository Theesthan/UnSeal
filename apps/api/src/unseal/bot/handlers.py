"""Handler registration plus /start, consent, /cases, /delete, retries and errors.

The conversation (in-memory `ConversationHandler`):
  /start -> LANGUAGE -> CONSENT -> DESCRIBE -> FOLLOW_UP (at most two) -> AUTHORITY
  (-> AUTHORITY_NAME -> AUTHORITY_ADDRESS -> JURISDICTION) -> CONFIRM -> REVIEW (EDIT,
  NEW_QUESTION) -> NAME -> ADDRESS -> BPL -> PAYMENT (skipped when BPL) -> PLACE -> PDF ->
  FILED_DATE -> FILED_MODE -> deadlines, end.
/cases and /delete work inside and outside the conversation. Nothing is stored before the user
taps "I agree". ponytail: conversation state lives in process memory, so it is lost on restart
and is per process; cases already saved stay in the database and /cases still lists them.
"""

import functools
import logging
import warnings
from collections.abc import Callable, Coroutine
from datetime import date
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

from unseal.bot import finish, flow
from unseal.bot.common import (
    Ctx,
    S,
    button,
    chat_id,
    clear_flow,
    current_user,
    data,
    keyboard,
    lang,
    say,
    send,
    services,
    tapped,
)
from unseal.bot.finish import shown_date
from unseal.bot.texts import LANGUAGE_BUTTONS, label, language_of, t
from unseal.services.cases import NotFound, case_summary, list_cases
from unseal.services.identity import delete_user, telegram_user

log = logging.getLogger("unseal.bot")

Callback = Callable[[Update, Ctx], Coroutine[Any, Any, int | None]]


def case_errors(callback: Callback) -> Callback:
    """A case that vanished (deleted, or lost after a restart) is explained, not crashed on."""

    @functools.wraps(callback)
    async def wrapped(update: Update, context: Ctx) -> int | None:
        try:
            return await callback(update, context)
        except NotFound:
            await say(update, context, "not_found")
            clear_flow(context)
            return ConversationHandler.END

    return wrapped


# ---------------------------------------------------------------- start and consent


async def start(update: Update, context: Ctx) -> int:
    clear_flow(context)
    rows = [[(label, f"lang:{code}")] for code, label in LANGUAGE_BUTTONS]
    await send(update, context, t("choose_language", "en"), keyboard(rows))
    return S.LANGUAGE


async def choose_language(update: Update, context: Ctx) -> int:
    data(context)["lang"] = language_of((await tapped(update)).removeprefix("lang:"))
    query = update.callback_query
    assert query is not None
    agree_row = [[button(context, "agree", "consent:yes")]]
    await query.edit_message_text(t("privacy", lang(context)), reply_markup=keyboard(agree_row))
    return S.CONSENT


async def agree(update: Update, context: Ctx) -> int:
    """Consent given: only now is a user row created (or found) for this chat."""
    await tapped(update)
    svc = services(context)
    key = svc.settings.telegram_chat_hash_key
    assert key is not None
    async with svc.session_factory() as session:
        user = await telegram_user(session, chat_id(update), key=key, language=lang(context))
        user.language = lang(context)
        await session.commit()
    log.info("telegram user consented")
    await say(update, context, "describe")
    return S.DESCRIBE


# ---------------------------------------------------------------- /cases and /delete


async def _known_language(update: Update, context: Ctx) -> bool:
    """Load the user's stored language into the flow when memory has none (after a restart).
    False when no user exists for this chat."""
    async with services(context).session_factory() as session:
        user = await current_user(session, update, context)
    if user is None:
        return False
    data(context).setdefault("lang", user.language)
    return True


async def cases_command(update: Update, context: Ctx) -> None:
    """Each case with its status and next deadline (FR-7)."""
    async with services(context).session_factory() as session:
        user = await current_user(session, update, context)
        listed = await list_cases(session, user) if user else []
    if user is not None:
        data(context).setdefault("lang", user.language)
    if not listed:
        await say(update, context, "no_cases")
        return
    language = lang(context)
    lines = [t("cases_header", language)]
    for number, case in enumerate(listed, start=1):
        summary = case_summary(case)
        authority = summary["authority_name"] or t("no_authority", language)
        status = label("status", summary["status"], language)
        lines.append(t("case_line", language, n=number, authority=authority, status=status))
        upcoming = summary["next_deadline"]
        if upcoming:
            due = shown_date(
                date.fromisoformat(upcoming["due_on"]), upcoming["estimated"], language
            )
            kind = label("kind", upcoming["kind"], language)
            lines.append(t("case_next", language, kind=kind, date=due))
    await send(update, context, "\n".join(lines))


async def delete_command(update: Update, context: Ctx) -> None:
    if not await _known_language(update, context):
        await say(update, context, "nothing_stored")
        return
    rows = [
        [button(context, "delete_yes", "del:yes")],
        [button(context, "delete_no", "del:no")],
    ]
    await say(update, context, "delete_confirm", keyboard(rows))


async def delete_confirm(update: Update, context: Ctx) -> int | None:
    """FR-8: every row and stored file of this user, then the conversation and memory too."""
    if (await tapped(update)) != "del:yes":
        await say(update, context, "kept")
        return None
    svc = services(context)
    async with svc.session_factory() as session:
        user = await current_user(session, update, context)
        if user is None:
            await say(update, context, "nothing_stored")
            return ConversationHandler.END
        language = language_of(data(context).get("lang") or user.language)
        await delete_user(session, user, svc.settings.storage_dir)
    data(context).clear()
    log.info("telegram user deleted their data")
    await send(update, context, t("deleted", language))
    return ConversationHandler.END


# ---------------------------------------------------------------- retries, strays and errors


async def retry(update: Update, context: Ctx) -> int | None:
    """Re-run the model step that was busy or cut off (kept in memory as `pending`)."""
    await tapped(update)
    pending: dict[str, str] | None = data(context).get("pending")
    if not pending:
        await say(update, context, "stale")
        return None
    if pending["kind"] == "intake":
        return await flow.intake_step(update, context, pending["text"])
    if pending["kind"] == "question":
        return await flow.question_step(update, context, pending["text"])
    return await finish.application_step(update, context, pending["place"])


async def unexpected(update: Update, context: Ctx) -> None:
    await say(update, context, "use_buttons")


async def stale(update: Update, context: Ctx) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer(t("stale", lang(context)))


async def still_working(update: Update, context: Ctx) -> None:
    if update.callback_query:
        await update.callback_query.answer(t("still_working", lang(context)))
        return
    await say(update, context, "still_working")


async def need_start(update: Update, context: Ctx) -> None:
    if update.callback_query:
        await update.callback_query.answer(t("need_start", lang(context)))
        return
    await say(update, context, "need_start")


async def on_error(update: object, context: Ctx) -> None:
    """Log the error type only (exception text can hold user text); apologise in plain words."""
    log.error("telegram update failed: %s", type(context.error).__name__)
    if not isinstance(update, Update) or update.effective_chat is None:
        return
    language = language_of((context.user_data or {}).get("lang"))
    try:
        await context.bot.send_message(update.effective_chat.id, t("error", language))
    except TelegramError as exc:
        log.warning("telegram apology not sent: %s", type(exc).__name__)


# ---------------------------------------------------------------- registration


def _tap(callback: Callback, pattern: str) -> CallbackQueryHandler[Ctx, int | None]:
    return CallbackQueryHandler(case_errors(callback), pattern=pattern)


def _text(callback: Callback) -> MessageHandler[Ctx, int | None]:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, case_errors(callback))


def conversation(*, block: bool) -> ConversationHandler[Ctx]:
    states: dict[object, list[BaseHandler[Update, Ctx, Any]]] = {
        S.LANGUAGE: [_tap(choose_language, r"^lang:(en|hi|ta)$")],
        S.CONSENT: [_tap(agree, r"^consent:yes$")],
        S.DESCRIBE: [_text(flow.describe)],
        S.FOLLOW_UP: [_text(flow.follow_up)],
        S.AUTHORITY: [_tap(flow.pick_authority, r"^auth:(\d|other)$")],
        S.AUTHORITY_NAME: [_text(flow.authority_name)],
        S.AUTHORITY_ADDRESS: [_text(flow.authority_address)],
        S.JURISDICTION: [_tap(flow.pick_jurisdiction, r"^jur:(central|tamil_nadu)$")],
        S.CONFIRM: [
            _tap(flow.confirm_authority, r"^authok$"),
            _tap(flow.change_authority, r"^authchange$"),
        ],
        S.REVIEW: [
            _tap(flow.accept, r"^q:accept:[0-9a-f-]{36}$"),
            _tap(flow.edit, r"^q:edit:[0-9a-f-]{36}$"),
            _tap(flow.add, r"^q:add$"),
            _tap(flow.done, r"^q:done$"),
        ],
        S.EDIT: [_text(flow.edited)],
        S.NEW_QUESTION: [_text(flow.new_question)],
        S.NAME: [_text(finish.applicant_name)],
        S.ADDRESS: [_text(finish.applicant_address)],
        S.BPL: [_tap(finish.bpl, r"^bpl:(yes|no)$")],
        S.PAYMENT: [_tap(finish.payment, r"^pay:[a-z_]{1,40}$")],
        S.PLACE: [_text(finish.place)],
        S.FILED_DATE: [_text(finish.filed_date)],
        S.FILED_MODE: [_tap(finish.filed_mode, r"^mode:(rti_online|post|in_person)$")],
        ConversationHandler.WAITING: [
            MessageHandler(filters.ALL, still_working),
            CallbackQueryHandler(still_working),
        ],
    }
    private = filters.ChatType.PRIVATE
    fallbacks: list[BaseHandler[Update, Ctx, Any]] = [
        CommandHandler("cases", cases_command, filters=private),
        CommandHandler("delete", delete_command, filters=private),
        _tap(delete_confirm, r"^del:(yes|no)$"),
        _tap(retry, r"^retry$"),
        MessageHandler(filters.ALL, unexpected),
        CallbackQueryHandler(stale),
    ]
    with warnings.catch_warnings():  # buttons are tracked per chat, not per message: intended
        warnings.filterwarnings("ignore", message=".*per_message.*", category=PTBUserWarning)
        return ConversationHandler(
            entry_points=[CommandHandler("start", start, filters=private)],
            states=states,
            fallbacks=fallbacks,
            allow_reentry=True,
            block=block,
            name="unseal",
        )


def register(application: Any, *, block: bool) -> None:
    """Every handler, in order: the conversation first, then the commands and catch-alls for
    chats with no conversation running."""
    private = filters.ChatType.PRIVATE
    application.add_handler(conversation(block=block))
    application.add_handler(CommandHandler("cases", cases_command, filters=private))
    application.add_handler(CommandHandler("delete", delete_command, filters=private))
    application.add_handler(CallbackQueryHandler(delete_confirm, pattern=r"^del:(yes|no)$"))
    application.add_handler(MessageHandler(private, need_start))
    application.add_handler(CallbackQueryHandler(need_start))
    application.add_error_handler(on_error)
