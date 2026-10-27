"""Builds the python-telegram-bot Application from settings and the injected services.

Webhook mode (inside the API, `api/telegram.py`): no updater; the webhook route puts updates on
`application.update_queue`. Polling mode (`python -m unseal.bot --polling`): PTB's updater.
Handlers run non-blocking (`block=False`) so one user's slow model call (BharatCode can take a
minute or more) never holds up anyone else; a user's extra messages meanwhile get "still working".
"""

from typing import Any

from telegram.ext import Application
from telegram.request import BaseRequest

from unseal.bot.handlers import register
from unseal.bot.logs import quiet_library_logs
from unseal.bot.services import BotServices, ChatQuota

__all__ = ["BotApplication", "BotServices", "build_application"]

BotApplication = Application[Any, Any, Any, Any, Any, Any]


def build_application(
    services: BotServices,
    *,
    request: BaseRequest | None = None,
    get_updates_request: BaseRequest | None = None,
    block: bool = False,
    polling: bool = False,
) -> BotApplication:
    """`request` objects replace PTB's HTTP client (tests pass a recording fake); `block=True`
    runs handlers inline, which tests use to step through a conversation deterministically."""
    token = services.settings.telegram_bot_token
    if token is None:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    builder: Any = Application.builder().token(token.get_secret_value()).job_queue(None)
    if request is not None:
        builder = builder.request(request)
    if get_updates_request is not None:
        builder = builder.get_updates_request(get_updates_request)
    if not polling:
        builder = builder.updater(None)
    quiet_library_logs()
    application: BotApplication = builder.build()
    application.bot_data["services"] = services
    application.bot_data["quota"] = ChatQuota(services.settings.rate_limit_model)
    register(application, block=block)
    return application
