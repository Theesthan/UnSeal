"""Log redaction: mask personal identifiers and bot tokens before a log handler writes them.

`redact(text)` masks, with fixed tokens:
  * Telegram bot tokens (`<digits>:<35+ url-safe chars>`, which leak through HTTP client logs as
    `api.telegram.org/bot<token>/...`)           -> `[token]`
  * email addresses                                -> `[email]`
  * Indian phone numbers: mobiles (6-9 first digit, optional +91 / 0091 / 91 / 0 prefix, spaces or
    hyphens between digit groups) and landlines with STD codes (`044-24341234`)   -> `[phone]`
  * 12-digit ID-like numbers (Aadhaar shape), joined or in 4-4-4 groups            -> `[id]`

Design decisions:
  * Tamil, Devanagari and other Unicode digits count as digits. Matching runs on a copy where
    every non-ASCII decimal digit is folded to its ASCII value (same length), and the masks are
    cut out of the ORIGINAL text, so surrounding Tamil and Hindi text is never altered.
  * A number glued to ASCII letters or digits is not masked (hex request ids, UUIDs, base64),
    nor is a UUID's last group or a decimal fraction. Non-ASCII letters do not glue: Hindi or
    Tamil text attached to a number does not hide it.
  * Every pattern is anchored at the start of a run, so matching is linear in the input size.
  * A bare 10-digit number starting 6-9 cannot be told from a mobile and is masked (so is a
    Telegram chat id of that shape). That is the safe direction for a privacy filter.

Names, addresses and grievance text are NOT detected: they must never be logged at all.

`RedactingFilter` redacts the final message (after `%` args formatting), exception tracebacks and
stack info. `install_redaction()` attaches it to the HANDLERS of a logger: a filter on a logger
does not apply to records from its child loggers, a filter on a handler does.
"""

import logging
import re
import unicodedata
from typing import Final

PHONE_MASK: Final = "[phone]"
EMAIL_MASK: Final = "[email]"
ID_MASK: Final = "[id]"
TOKEN_MASK: Final = "[token]"
WITHHELD_MESSAGE: Final = "[log message withheld: redaction failed]"
_UNPRINTABLE: Final = "<unprintable>"

# ---- patterns (all matching runs on digit-folded text, so [0-9] is enough) ------------------

_SEP = r"[  -]"  # between digit groups: a space, a no-break space or a hyphen
_HEX = "[0-9A-Fa-f]"
# A number is not masked when glued to ASCII letters or digits (hex ids, base64) or when it is a
# decimal fraction ("0.123456789012", "123456789012.5").
_NOT_GLUED_BEFORE = r"(?<![0-9A-Za-z])(?<![0-9]\.)"
_NOT_GLUED_AFTER = r"(?![0-9A-Za-z])(?!\.[0-9])"
# UUIDs end in 12 hex chars (often all digits) and can have 4-digit groups in the middle.
_NOT_UUID_TAIL = rf"(?<!{_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-)"
_NOT_UUID_MIDDLE = rf"(?<!{_HEX}{{8}}-)"


def _digits(count: int) -> str:
    return f"[0-9]{{{count}}}"


def _grouped(sizes: tuple[int, ...], first: str = "[0-9]") -> str:
    """Digit groups of the given sizes, a separator between groups; `first` is the first digit."""
    head = f"{first}{_digits(sizes[0] - 1)}" if sizes[0] > 1 else first
    return _SEP.join([head, *(_digits(size) for size in sizes[1:])])


# Telegram bot token: <bot id>:<secret>. "bot" may be glued in front (`/bot123:AA...`).
_TOKEN = r"(?<![0-9])[0-9]{5,15}:[A-Za-z0-9_-]{35,}"

# Email: the local part is any run without whitespace or delimiters (so Hindi or Tamil text glued
# to it is swallowed, never leaked); the domain is ASCII. Anchored at the start of the run.
_LOCAL_CHAR = r"[^\s@<>()\[\]{}\"'`,;:!?/\\|=&#*]"
_EMAIL = rf"(?<!{_LOCAL_CHAR}){_LOCAL_CHAR}+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{{2,}}"

# Country prefix: +91, (+91), 0091 or a bare 91, then an optional separator.
_COUNTRY = rf"(?:\(?\+91\)?|(?:00)?91){_SEP}?"

# Mobile: 10 digits starting 6-9, written in one run or in groups, with an optional prefix.
_MOBILE_GROUPINGS: Final = ((10,), (5, 5), (4, 3, 3), (3, 3, 4), (3, 4, 3))
_MOBILE_NUMBER = "|".join(_grouped(sizes, first="[6-9]") for sizes in _MOBILE_GROUPINGS)
_MOBILE = rf"(?:{_COUNTRY}|0{_SEP}?)?(?:{_MOBILE_NUMBER})"

# Landline: STD code + subscriber number are 10 digits together, behind a 0 (or a country code).
_LANDLINE_SPLITS: Final = ((2, 8), (3, 7), (4, 6))  # (STD digits, subscriber digits)


def _subscriber_forms(count: int) -> list[str]:
    """A subscriber number in one run, or in two groups of about half each."""
    low, high = count // 2, count - count // 2
    forms = [_digits(count), f"{_digits(low)}{_SEP}{_digits(high)}"]
    if low != high:
        forms.append(f"{_digits(high)}{_SEP}{_digits(low)}")
    return forms


_LANDLINE_BODY = "|".join(
    rf"[1-9]{_digits(std - 1)}\)?{_SEP}?{number}"
    for std, subscriber in _LANDLINE_SPLITS
    for number in _subscriber_forms(subscriber)
)
_LANDLINE = rf"(?:{_COUNTRY}\(?|\(?0)(?:{_LANDLINE_BODY})"

_PHONE = rf"{_NOT_GLUED_BEFORE}{_NOT_UUID_TAIL}(?:{_MOBILE}|{_LANDLINE}){_NOT_GLUED_AFTER}"

# 12-digit ID-like number: joined, or in 4-4-4 groups.
_ID = (
    rf"{_NOT_GLUED_BEFORE}(?:{_NOT_UUID_TAIL}{_digits(12)}|{_NOT_UUID_MIDDLE}{_grouped((4, 4, 4))})"
    rf"{_NOT_GLUED_AFTER}"
)

# One pass, leftmost match wins; at one position the alternatives are tried in this order, so a
# phone-like local part inside an email is part of the email.
_MASKS: Final = {"token": TOKEN_MASK, "email": EMAIL_MASK, "phone": PHONE_MASK, "id": ID_MASK}
_BODIES: Final = {"token": _TOKEN, "email": _EMAIL, "phone": _PHONE, "id": _ID}
_PATTERN: Final = re.compile("|".join(f"(?P<{name}>{_BODIES[name]})" for name in _MASKS))

_NON_ASCII_DIGIT = re.compile(r"(?![0-9])\d")  # \d is any Unicode decimal digit (Tamil, ...)


def _fold_digits(text: str) -> str:
    """Same-length copy with every non-ASCII decimal digit replaced by its ASCII digit."""
    if text.isascii():
        return text
    return _NON_ASCII_DIGIT.sub(lambda m: str(unicodedata.digit(m.group())), text)


def redact(text: str) -> str:
    """Return `text` with phone numbers, emails, ID-like numbers and bot tokens masked."""
    folded = _fold_digits(text)
    pieces: list[str] = []
    last = 0
    for match in _PATTERN.finditer(folded):
        pieces.append(text[last : match.start()])
        pieces.append(_MASKS.get(match.lastgroup or "", "[redacted]"))
        last = match.end()
    if last == 0:  # no match (a match is never empty)
        return text
    pieces.append(text[last:])
    return "".join(pieces)


# ---- logging --------------------------------------------------------------------------------

_TRACEBACK_FORMATTER: Final = logging.Formatter()


def _safe_str(value: object) -> str:
    try:
        return str(value)
    except Exception:
        return _UNPRINTABLE


def _message(record: logging.LogRecord) -> str:
    """The final message, `%` args applied. Bad args keep the template and the args' text."""
    try:
        return record.getMessage()
    except Exception:
        return (
            f"{_safe_str(record.msg)} "
            f"(log record could not be formatted, args={_safe_str(record.args)})"
        )


def _exception_text(record: logging.LogRecord) -> str | None:
    """The traceback as a handler's formatter would print it (or the text already cached)."""
    text = record.exc_text
    if not text and record.exc_info:
        text = _TRACEBACK_FORMATTER.formatException(record.exc_info)
    return redact(text) if text else None


def _redact_record(record: logging.LogRecord) -> None:
    # Compute everything first, then assign: a failure half way leaves the record untouched.
    message = redact(_message(record))
    exc_text = _exception_text(record)
    stack_info = redact(record.stack_info) if record.stack_info else None
    record.msg = message
    record.args = None  # already applied; nothing is left for a handler to re-format
    record.exc_text = exc_text
    record.exc_info = None  # a handler must not re-format the raw traceback
    record.stack_info = stack_info


def _withhold(record: logging.LogRecord) -> None:
    """Fail closed: log that something happened, never the unredacted content."""
    record.msg = WITHHELD_MESSAGE
    record.args = None
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None


class RedactingFilter(logging.Filter):
    """Masks the final message, the traceback and the stack info of every record it sees.

    Never raises and never drops a record. If redaction itself fails, the record's content is
    replaced by `WITHHELD_MESSAGE`. Attach it to handlers (`install_redaction`), not loggers.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            _redact_record(record)
        except Exception:
            _withhold(record)
        return True


def install_redaction(logger: logging.Logger | None = None) -> None:
    """Attach one `RedactingFilter` to every handler of `logger` (default: the root logger).

    Idempotent. Only handlers that exist at call time are covered: call it again after adding
    handlers, and pass loggers that do not propagate to root (for example `uvicorn.access`).
    """
    target = logger if logger is not None else logging.getLogger()
    for handler in target.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
