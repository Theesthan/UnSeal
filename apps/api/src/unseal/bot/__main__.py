"""`python -m unseal.bot --polling`: the bot standalone, for local development, against the same
database as the API (DATABASE_URL). Polling removes any webhook set for this token, so use a
separate development bot, not the production one."""

import argparse
import logging
import sys

from telegram import Update

from unseal.bot.app import BotServices, build_application
from unseal.config import Settings
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import build_client
from unseal.pdf.render import render_application_pdf
from unseal.privacy.redact import install_redaction

log = logging.getLogger("unseal.bot")


def main(argv: list[str] | None = None, *, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m unseal.bot", description=__doc__)
    parser.add_argument("--polling", action="store_true", help="poll Telegram for updates")
    if not parser.parse_args(argv).polling:
        parser.print_usage(sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO)
    install_redaction()  # masks phone numbers, emails and bot tokens in what is logged
    config = settings or Settings()
    if config.telegram_bot_token is None or config.telegram_chat_hash_key is None:
        log.error("set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_HASH_KEY to run the bot")
        return 1
    services = BotServices(
        settings=config,
        session_factory=build_session_factory(build_engine(config.database_url.get_secret_value())),
        llm=build_client(config),
        renderer=render_application_pdf,
    )
    build_application(services, polling=True).run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
