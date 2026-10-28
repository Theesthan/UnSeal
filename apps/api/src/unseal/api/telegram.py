"""Telegram webhook (docs/api.md "Telegram") and the bot's start and stop in the API lifespan.

The secret header is compared in constant time BEFORE the body is parsed or anything else runs
(CLAUDE.md security checklist; pentest item 1). An accepted update goes onto the bot's queue and
the route answers 200 at once, so Telegram never retries a slow model call into duplicates; a
redelivered update id is dropped.
"""

import hmac
import json
import logging
from collections import deque

from fastapi import APIRouter, FastAPI, Request, Response
from pydantic import SecretStr
from telegram import Update
from telegram.error import TelegramError
from telegram.request import BaseRequest

from unseal.api.errors import error_response
from unseal.bot.app import BotApplication, BotServices, build_application
from unseal.bot.reminders import reminder_sender as bot_reminder_sender
from unseal.config import Settings
from unseal.scheduler import Send

log = logging.getLogger(__name__)

router = APIRouter()

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
RECENT_UPDATES = 4096


class RecentUpdates:
    """Update ids already accepted, to drop Telegram redeliveries.
    ponytail: in memory, per process, last RECENT_UPDATES ids only."""

    def __init__(self, size: int = RECENT_UPDATES) -> None:
        self._order: deque[int] = deque()
        self._ids: set[int] = set()
        self._size = size

    def first_time(self, update_id: int) -> bool:
        if update_id in self._ids:
            return False
        if len(self._order) >= self._size:
            self._ids.discard(self._order.popleft())
        self._order.append(update_id)
        self._ids.add(update_id)
        return True


def secret_matches(given: str | None, expected: SecretStr | None) -> bool:
    if expected is None or not given:
        return False
    return hmac.compare_digest(given.encode(), expected.get_secret_value().encode())


@router.post("/telegram/webhook")
async def webhook(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    application: BotApplication | None = getattr(request.app.state, "telegram", None)
    if settings.telegram_bot_token is None or application is None:
        return error_response(404, "not_found")
    if not secret_matches(request.headers.get(SECRET_HEADER), settings.telegram_webhook_secret):
        return error_response(403, "bad_secret")
    try:
        payload = json.loads(await request.body())
        valid = isinstance(payload, dict) and type(payload.get("update_id")) is int
        update = Update.de_json(payload, application.bot) if valid else None
    except (ValueError, TypeError, KeyError, AttributeError):
        update = None
    if update is None:
        return error_response(400, "invalid")
    seen: RecentUpdates = request.app.state.telegram_seen
    if seen.first_time(update.update_id):
        await application.update_queue.put(update)
    return Response(status_code=200)


def _missing(app: FastAPI, settings: Settings) -> list[str]:
    checks = {
        "TELEGRAM_WEBHOOK_SECRET": settings.telegram_webhook_secret,
        "TELEGRAM_CHAT_HASH_KEY": settings.telegram_chat_hash_key,
        "model client": app.state.llm,
    }
    return [name for name, value in checks.items() if value is None]


async def start_bot(app: FastAPI, *, request: BaseRequest | None = None) -> None:
    """Start the bot in webhook mode when TELEGRAM_BOT_TOKEN is set. Missing settings or an
    unreachable Telegram leave the bot off (the webhook answers 404) but never stop the API."""
    app.state.telegram = None
    settings: Settings = app.state.settings
    if settings.telegram_bot_token is None:
        return
    if missing := _missing(app, settings):
        log.error("telegram bot disabled: %s not set", ", ".join(missing))
        return
    services = BotServices(
        settings=settings,
        session_factory=app.state.session_factory,
        llm=app.state.llm,
        renderer=app.state.renderer,
    )
    application = build_application(services, request=request)
    try:
        await application.initialize()
        await application.start()
    except TelegramError as exc:
        log.error("telegram bot disabled: could not start (%s)", type(exc).__name__)
        return
    app.state.telegram_seen = RecentUpdates()
    app.state.telegram = application


def reminder_sender(app: FastAPI) -> Send | None:
    """The scheduler's sender when the bot is running, else None (then nothing is claimed)."""
    application: BotApplication | None = getattr(app.state, "telegram", None)
    if application is None:
        return None
    return bot_reminder_sender(application.bot, app.state.session_factory)


async def stop_bot(app: FastAPI) -> None:
    application: BotApplication | None = getattr(app.state, "telegram", None)
    app.state.telegram = None
    if application is None:
        return
    if application.running:
        await application.stop()
    await application.shutdown()
