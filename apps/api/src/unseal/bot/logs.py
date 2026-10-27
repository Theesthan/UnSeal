"""Keep library logs that carry message content out of the logs (CLAUDE.md: never log message
text; pentest item 9).

python-telegram-bot logs every incoming update ("Processing update ...") and every Bot API call
with its parameters (chat id, message text) at DEBUG; httpx logs each request URL, which holds the
bot token, at INFO. Pinning those loggers keeps that out even when the app runs at DEBUG.
"""

import logging

_FLOORS = {"telegram": logging.INFO, "httpx": logging.WARNING}


def quiet_library_logs() -> None:
    for name, floor in _FLOORS.items():
        logger = logging.getLogger(name)
        if logger.level == logging.NOTSET or logger.level < floor:
            logger.setLevel(floor)
