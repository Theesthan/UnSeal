"""Log redaction: phone numbers, emails, 12-digit ID-like numbers and Telegram bot tokens.

Only fictional values appear here (CLAUDE.md golden rule 3). The filter is tested through real
logging handlers, because that is where a leak would happen.
"""

import importlib
import inspect
import logging
import sys
import time
import uuid
from collections.abc import Iterator

import pytest

from unseal.privacy.redact import RedactingFilter, install_redaction, redact

redact_module = importlib.import_module("unseal.privacy.redact")

TAMIL_ZERO = 0x0BE6
DEVANAGARI_ZERO = 0x0966


def _in_script(ascii_digits: str, zero: int) -> str:
    """Write ASCII digits with the digit glyphs of another script (Tamil, Devanagari)."""
    return "".join(chr(zero + int(d)) for d in ascii_digits)


def _tamil(ascii_digits: str) -> str:
    return _in_script(ascii_digits, TAMIL_ZERO)


def _hindi(ascii_digits: str) -> str:
    return _in_script(ascii_digits, DEVANAGARI_ZERO)


_SECRET = ("Fake_Tok-0123456789" * 2)[:35]
assert len(_SECRET) == 35
_TOKEN = "123456789:" + _SECRET

# --------------------------------------------------------------------------------------------
# redact(): what must be masked
# --------------------------------------------------------------------------------------------

MUST_MASK = [
    # Indian mobiles: optional +91 / 0091 / 91 / 0 prefix, optional spaces or hyphens
    ("mobile_plain", "9876543210", "[phone]"),
    ("mobile_plus91_spaced", "+91 98765 43210", "[phone]"),
    ("mobile_plus91_joined", "+919876543210", "[phone]"),
    ("mobile_plus91_hyphen", "+91-9876543210", "[phone]"),
    ("mobile_plus91_bracketed", "(+91) 98765 43210", "[phone]"),
    ("mobile_0091", "0091 9876543210", "[phone]"),
    ("mobile_91_bare", "919876543210", "[phone]"),
    ("mobile_91_spaced", "91 98765 43210", "[phone]"),
    ("mobile_zero_prefix_hyphen", "098765-43210", "[phone]"),
    ("mobile_zero_prefix_joined", "09876543210", "[phone]"),
    ("mobile_5_5", "98765 43210", "[phone]"),
    ("mobile_5_5_hyphen", "98765-43210", "[phone]"),
    ("mobile_4_3_3", "9876 543 210", "[phone]"),
    ("mobile_3_3_4", "987-654-3210", "[phone]"),
    ("mobile_3_4_3", "987 6543 210", "[phone]"),
    ("mobile_nbsp", "+91 98765 43210", "[phone]"),
    ("mobile_starts_6", "6123456789", "[phone]"),
    ("mobile_starts_7", "7123456789", "[phone]"),
    ("mobile_starts_8", "8123456789", "[phone]"),
    ("mobile_starting_91_itself", "9123456789", "[phone]"),
    # landlines with STD codes (2, 3 and 4 digit codes)
    ("landline_chennai", "044-24341234", "[phone]"),
    ("landline_chennai_spaced", "044 24341234", "[phone]"),
    ("landline_chennai_split", "044 2434 1234", "[phone]"),
    ("landline_chennai_joined", "04424341234", "[phone]"),
    ("landline_bracketed_std", "(044) 24341234", "[phone]"),
    ("landline_bracketed_std_joined", "(044)24341234", "[phone]"),
    ("landline_3_digit_std", "0422-2345678", "[phone]"),
    ("landline_3_digit_std_split", "0422 234 5678", "[phone]"),
    ("landline_4_digit_std", "04142-123456", "[phone]"),
    ("landline_4_digit_std_split", "04142 123 456", "[phone]"),
    ("landline_delhi", "011-23456789", "[phone]"),
    ("landline_intl", "+91-44-24341234", "[phone]"),
    ("landline_intl_spaced", "+91 44 2434 1234", "[phone]"),
    ("landline_intl_bracketed_std", "+91 (44) 24341234", "[phone]"),
    # emails
    ("email_plain", "test@example.com", "[email]"),
    ("email_dotted_plus", "first.last+tag@sub.example.co.in", "[email]"),
    ("email_digits_and_hyphens", "user-1_2@my-host.example.org", "[email]"),
    ("email_upper", "TEST@EXAMPLE.COM", "[email]"),
    ("email_phone_like_local", "9876543210@example.com", "[email]"),
    # 12-digit ID-like numbers (Aadhaar shape)
    ("id_spaced", "1234 5678 9012", "[id]"),
    ("id_hyphen", "1234-5678-9012", "[id]"),
    ("id_joined", "123456789012", "[id]"),
    ("id_mixed_separators", "1234 5678-9012", "[id]"),
    ("id_nbsp", "1234 5678 9012", "[id]"),
    ("id_leading_zero", "012345678901", "[id]"),
    ("id_starts_like_a_mobile", "987654321098", "[id]"),
    # Telegram bot tokens
    ("token_alone", _TOKEN, "[token]"),
    (
        "token_in_bot_url",
        f"https://api.telegram.org/bot{_TOKEN}/getMe",
        "https://api.telegram.org/bot[token]/getMe",
    ),
    ("token_longer_secret", _TOKEN + "xyz", "[token]"),
    ("token_short_bot_id", "12345:" + _SECRET, "[token]"),
    # Tamil and Devanagari digits are masked like ASCII digits
    ("tamil_mobile", _tamil("9876543210"), "[phone]"),
    ("tamil_mobile_plus91", "+" + _tamil("91") + " " + _tamil("9876543210"), "[phone]"),
    ("tamil_mobile_spaced", _tamil("98765") + " " + _tamil("43210"), "[phone]"),
    ("tamil_landline", _tamil("044") + "-" + _tamil("24341234"), "[phone]"),
    ("tamil_id", " ".join(_tamil(g) for g in ("1234", "5678", "9012")), "[id]"),
    ("hindi_mobile", _hindi("9876543210"), "[phone]"),
    ("hindi_id", _hindi("123456789012"), "[id]"),
    ("mixed_script_mobile", _tamil("98765") + "43210", "[phone]"),
    ("fullwidth_mobile", "".join(chr(0xFF10 + int(d)) for d in "9876543210"), "[phone]"),
    # context: what surrounds a value is kept, the value goes
    ("ctx_sentence", "call me on 9876543210.", "call me on [phone]."),
    ("ctx_label", "Aadhaar: 1234 5678 9012, ok", "Aadhaar: [id], ok"),
    ("ctx_query_string", "phone=9876543210&x=1", "phone=[phone]&x=1"),
    ("ctx_url_path", "https://wa.me/919876543210?text=hi", "https://wa.me/[phone]?text=hi"),
    ("ctx_underscore", "user_9876543210", "user_[phone]"),
    ("ctx_brackets", "(9876543210)", "([phone])"),
    ("ctx_email_in_angle_brackets", "Name <test@example.com>", "Name <[email]>"),
    ("ctx_email_trailing_dot", "write to test@example.com.", "write to [email]."),
    ("ctx_email_in_url", "/send?to=test@example.com&x=1", "/send?to=[email]&x=1"),
    ("ctx_two_values", "9876543210 and test@example.com", "[phone] and [email]"),
    ("ctx_two_phones", "9876543210, 9123456780", "[phone], [phone]"),
    (
        "ctx_all_four",
        f"{_TOKEN} 9876543210 test@example.com 1234 5678 9012",
        "[token] [phone] [email] [id]",
    ),
    ("ctx_hindi_sentence", "मेरा नंबर 9876543210 है", "मेरा नंबर [phone] है"),
    ("ctx_hindi_attached", _hindi("9876543210") + "पर", "[phone]पर"),
    ("ctx_tamil_sentence", f"என் எண் {_tamil('9876543210')} ஆகும்", "என் எண் [phone] ஆகும்"),
    ("ctx_tamil_attached_email", "மின்னஞ்சல்:test@example.comஐ", "மின்னஞ்சல்:[email]ஐ"),
    ("ctx_multiline", "a\n9876543210\nb", "a\n[phone]\nb"),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [pytest.param(text, expected, id=name) for name, text, expected in MUST_MASK],
)
def test_masks_personal_identifiers(text: str, expected: str) -> None:
    assert redact(text) == expected


# --------------------------------------------------------------------------------------------
# redact(): what must NOT be masked
# --------------------------------------------------------------------------------------------

UUID_WITH_DIGIT_TAIL = "550e8400-e29b-41d4-a716-446655440000"

MUST_NOT_MASK = [
    ("iso_date", "2026-08-03"),
    ("iso_datetime", "2026-08-03T09:15:00+05:30"),
    ("date_and_time", "on 2026-08-03 at 09:15:00"),
    ("two_dates", "2026-08-03 2026-08-04"),
    ("compact_date", "20260803"),
    ("dd_mm_yyyy", "03-08-2026"),
    ("uuid", "123e4567-e89b-12d3-a456-426614174000"),
    ("uuid_with_12_digit_tail", UUID_WITH_DIGIT_TAIL),
    ("uuid_with_digit_groups", "550e8400-1234-5678-9012-446655440000"),
    ("uuid_with_phone_like_tail", "123e4567-e89b-12d3-a456-919876543210"),
    ("uuid_uppercase", "123E4567-E89B-12D3-A456-426614174000"),
    ("uuid_in_sentence", f"case {UUID_WITH_DIGIT_TAIL} opened"),
    ("uuid_hex_without_hyphens", "123e4567e89b12d3a456426614174000"),
    ("request_id_hex", "req_8f14e45fceea167a5a36dedd4bea2543"),
    ("request_id_header", "x-request-id: 3b7c9e2a-5d41-4f68-9a0b-c2d4e6f80a1b"),
    ("request_id_ulid", "req_01HZX3F8KMNPQRSTVWXYZABCDE"),
    ("request_id_letters_around_digits", "ab123456789012cd"),
    ("request_id_letters_around_mobile", "ab9876543210cd"),
    ("amount", "Rs 10"),
    ("amount_copies", "Rs 2 per page"),
    ("amounts_two", "Rs 10 and Rs 20"),
    ("amount_grouped", "Rs 9,87,65,43,210"),
    ("year", "year 2026"),
    ("year_range", "2025-2026"),
    ("case_number", "W.P.(C) 177/2026"),
    ("case_number_sentence", "see W.P.(C) 177/2026 dated 2026-08-03"),
    ("short_number", "12345"),
    ("short_numbers_list", "pages 7 8 9 10 11 12"),
    ("short_numbers_hyphen", "7-8-9"),
    ("section", "S. 19(3) within 90 days"),
    ("deadline", "reminder in 48 hours, 30 days, 500 words"),
    ("time", "10:20:30"),
    ("version", "v1.2.3"),
    ("ip_address", "192.168.100.200"),
    ("port", "localhost:8000"),
    ("nine_digits", "987654321"),
    ("eleven_digits_not_zero_prefixed", "98765432109"),
    ("thirteen_digits_epoch_ms", "1790000000000"),
    ("ten_digit_epoch_seconds", "1790000000"),
    ("ten_digits_not_a_mobile", "1234567890"),
    ("ten_digits_starting_5", "5876543210"),
    ("sixteen_digit_run", "1234567890123456"),
    ("decimal_fraction", "ratio 0.123456789012"),
    ("decimal_after_12_digits", "value 123456789012.5"),
    ("decimal_after_10_digits", "value 9876543210.5"),
    ("short_token_lookalike", "123456789:short"),
    ("clock_lookalike", "12:34"),
    ("no_digit_colon_run", "key: abcdefghijklmnopqrstuvwxyzabcdefghijklmnop"),
    ("not_an_email_at_sign", "meet @ 5pm, a @ b"),
    ("not_an_email_no_tld", "user@localhost"),
    ("plain_english", "The PIO must reply within thirty days."),
    ("tamil_prose", "தகவல் அறியும் உரிமைச் சட்டம்"),
    ("tamil_year_and_amount", "விண்ணப்பம் எண் " + _tamil("2026") + " கட்டணம் ரூ " + _tamil("10")),
    ("tamil_case_number", "W.P.(C) " + _tamil("177") + "/" + _tamil("2026")),
    ("tamil_short_number", _tamil("12345")),
    ("tamil_ten_digits_starting_5", _tamil("5876543210")),
    ("tamil_date", _tamil("2026") + "-" + _tamil("08") + "-" + _tamil("03")),
    ("hindi_prose", "सूचना का अधिकार अधिनियम"),
    (
        "hindi_year_and_amount",
        "आवेदन संख्या " + _hindi("77") + "/" + _hindi("2026") + " शुल्क रु " + _hindi("10"),
    ),
    ("hindi_date", _hindi("2026") + "-" + _hindi("08") + "-" + _hindi("03")),
    ("empty", ""),
    ("whitespace", "  \n\t "),
    ("already_redacted", "[phone] [email] [id] [token]"),
]


@pytest.mark.parametrize(
    "text",
    [pytest.param(text, id=name) for name, text in MUST_NOT_MASK],
)
def test_leaves_everything_else_alone(text: str) -> None:
    assert redact(text) == text


@pytest.mark.parametrize("text", ["9198 7654 3210", "9123 4567 8901", "919876543210"])
def test_a_91_prefixed_number_is_masked_whichever_way_it_reads(text: str) -> None:
    # "91" is both India's country code and a possible start of an ID: the label may differ.
    assert redact(text) in {"[phone]", "[id]"}


def test_redaction_is_idempotent() -> None:
    raw = f"{_TOKEN} +91 98765 43210 test@example.com 1234 5678 9012 044-24341234"
    once = redact(raw)
    assert once == "[token] [phone] [email] [id] [phone]"
    assert redact(once) == once


def test_masked_output_never_contains_the_value() -> None:
    for _, text, expected in MUST_MASK:
        if expected in {"[phone]", "[email]", "[id]", "[token]"}:
            assert redact(text) == expected
    out = redact(f"x {_TOKEN} y")
    assert _SECRET not in out
    assert "123456789" not in out


# Sized so linear matching takes ~0.1 s here, while a quadratic pattern (an email local part not
# anchored at the start of a run took 5 s at this size) fails the limit instead of hanging.
_N = 20_000


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * _N, id="long_word"),
        pytest.param("9" * _N, id="long_digits"),
        pytest.param("0" * _N, id="long_zeros"),
        pytest.param("9 " * _N, id="spaced_digits"),
        pytest.param("1-" * _N, id="hyphenated_digits"),
        pytest.param("98765 " * _N, id="repeated_mobile_halves"),
        pytest.param("a@" * _N, id="at_signs"),
        pytest.param("a@" + "a." * _N, id="long_dotted_domain"),
        pytest.param("a" * _N + "@", id="long_local_part"),
        pytest.param("a@" + "a" * _N, id="long_domain_label"),
        pytest.param("1" * _N + ":" + "x" * _N, id="digits_colon_word"),
        pytest.param(_tamil("9") * _N, id="long_tamil_digits"),
    ],
)
def test_adversarial_input_finishes_quickly(text: str) -> None:
    start = time.perf_counter()
    redact(text)
    assert time.perf_counter() - start < 1.0


def test_the_package_does_not_shadow_its_own_module() -> None:
    # Re-exporting the function `redact` from the package would hide the module `redact`.
    assert inspect.ismodule(redact_module)
    assert redact_module.redact is redact
    assert redact_module.RedactingFilter is RedactingFilter
    assert redact_module.install_redaction is install_redaction


# --------------------------------------------------------------------------------------------
# RedactingFilter: through real handlers
# --------------------------------------------------------------------------------------------


class _ListHandler(logging.Handler):
    """Collects what a real handler would write, after the filters and the formatter ran."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def logged() -> Iterator[tuple[logging.Logger, list[str]]]:
    """A child logger whose records reach a redacting handler on the PARENT logger.

    Filters on a logger do not apply to records from its children; filters on a handler do.
    Logging through the child proves the handler placement works.
    """
    parent = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    parent.setLevel(logging.DEBUG)
    parent.propagate = False
    handler = _ListHandler()
    parent.addHandler(handler)
    install_redaction(parent)
    child = logging.getLogger(parent.name + ".child")
    yield child, handler.lines
    parent.removeHandler(handler)


class _Url:
    """Like httpx's URL object: only __str__ reveals the secret."""

    def __str__(self) -> str:
        return f"https://api.telegram.org/bot{_TOKEN}/getMe"


class _Unprintable:
    def __str__(self) -> str:
        raise RuntimeError("no str")

    def __repr__(self) -> str:
        raise RuntimeError("no repr")


def test_filter_masks_percent_args(logged: tuple[logging.Logger, list[str]]) -> None:
    log, lines = logged
    log.info("user %s", "9876543210")
    log.info("a=%s b=%d c=%s", "test@example.com", 5, "1234 5678 9012")
    assert lines == ["INFO user [phone]", "INFO a=[email] b=5 c=[id]"]


def test_filter_masks_mapping_args(logged: tuple[logging.Logger, list[str]]) -> None:
    log, lines = logged
    log.info("who=%(who)s", {"who": "test@example.com"})
    assert lines == ["INFO who=[email]"]


def test_filter_masks_values_that_only_reveal_themselves_in_str(
    logged: tuple[logging.Logger, list[str]],
) -> None:
    log, lines = logged
    log.info('HTTP Request: %s %s "HTTP/1.1 200 OK"', "POST", _Url())
    assert lines == [
        'INFO HTTP Request: POST https://api.telegram.org/bot[token]/getMe "HTTP/1.1 200 OK"'
    ]


def test_filter_masks_a_message_that_is_not_a_string(
    logged: tuple[logging.Logger, list[str]],
) -> None:
    log, lines = logged
    log.info(ValueError("bad value 9876543210"))
    assert lines == ["INFO bad value [phone]"]


def test_filter_masks_a_literal_message_with_no_args(
    logged: tuple[logging.Logger, list[str]],
) -> None:
    log, lines = logged
    log.warning("sent to test@example.com")
    assert lines == ["WARNING sent to [email]"]


def test_filter_masks_exception_tracebacks(logged: tuple[logging.Logger, list[str]]) -> None:
    log, lines = logged
    try:
        raise ValueError("cannot deliver to test@example.com")
    except ValueError:
        log.exception("delivery failed for %s", "9876543210")
    (line,) = lines
    assert line.startswith("ERROR delivery failed for [phone]\nTraceback")
    assert "ValueError: cannot deliver to [email]" in line
    assert "test@example.com" not in line  # also gone from the echoed source line
    assert "9876543210" not in line


def test_filter_masks_exceptions_passed_as_exc_info(
    logged: tuple[logging.Logger, list[str]],
) -> None:
    log, lines = logged
    log.error("failed", exc_info=KeyError("1234 5678 9012"))
    (line,) = lines
    assert "KeyError" in line
    assert "[id]" in line
    assert "1234 5678 9012" not in line


def test_filter_masks_chained_exceptions(logged: tuple[logging.Logger, list[str]]) -> None:
    log, lines = logged
    try:
        try:
            raise ValueError("first for test@example.com")
        except ValueError as exc:
            raise RuntimeError("second for 9876543210") from exc
    except RuntimeError:
        log.exception("chain")
    (line,) = lines
    assert "ValueError: first for [email]" in line
    assert "RuntimeError: second for [phone]" in line
    assert "test@example.com" not in line
    assert "9876543210" not in line


def test_filter_masks_stack_info(logged: tuple[logging.Logger, list[str]]) -> None:
    log, lines = logged
    log.info("where", stack_info=True)
    (line,) = lines
    assert line.startswith("INFO where\nStack (most recent call last):")


def _record(
    msg: object,
    args: object = (),
    exc_info: object = None,
    stack_info: str | None = None,
) -> logging.LogRecord:
    return logging.LogRecord(
        "t",
        logging.ERROR,
        __file__,
        1,
        msg,
        args,
        exc_info,
        sinfo=stack_info,  # type: ignore[arg-type]
    )


def test_filter_rewrites_the_record_so_no_other_handler_sees_the_original() -> None:
    record = _record("user %s", ("9876543210",))
    assert RedactingFilter().filter(record) is True
    assert record.msg == "user [phone]"
    assert record.args is None
    assert record.getMessage() == "user [phone]"


def test_filter_drops_the_raw_exc_info_and_keeps_redacted_text() -> None:
    try:
        raise ValueError("bad test@example.com")
    except ValueError:
        record = _record("x", exc_info=sys.exc_info())
    RedactingFilter().filter(record)
    assert record.exc_info is None
    assert record.exc_text is not None
    assert "ValueError: bad [email]" in record.exc_text
    assert "test@example.com" not in record.exc_text


def test_filter_redacts_exception_text_cached_by_an_earlier_formatter() -> None:
    record = _record("x")
    record.exc_text = "Traceback ...\nValueError: bad test@example.com"
    RedactingFilter().filter(record)
    assert record.exc_text == "Traceback ...\nValueError: bad [email]"


def test_filter_redacts_stack_info() -> None:
    record = _record("x", stack_info="Stack (most recent call last):\n  line with 9876543210")
    RedactingFilter().filter(record)
    assert record.stack_info == "Stack (most recent call last):\n  line with [phone]"


def test_filter_leaves_clean_records_without_exception_untouched_apart_from_args() -> None:
    record = _record("plain %d", (5,))
    RedactingFilter().filter(record)
    assert record.getMessage() == "plain 5"
    assert record.exc_info is None
    assert record.exc_text is None
    assert record.stack_info is None


def test_filter_twice_gives_the_same_result() -> None:
    record = _record("user %s", ("test@example.com",))
    flt = RedactingFilter()
    flt.filter(record)
    flt.filter(record)
    assert record.getMessage() == "user [email]"


# --- never raises -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("msg", "args"),
    [
        pytest.param("user %d", ("abc 9876543210",), id="wrong_type"),
        pytest.param("a %s b %s", ("9876543210",), id="too_few_args"),
        pytest.param("a", ("9876543210",), id="too_many_args"),
        pytest.param("%(who)s", ({"other": "9876543210"},), id="missing_mapping_key"),
        pytest.param("100% sure %", ("9876543210",), id="stray_percent"),
    ],
)
def test_broken_format_args_do_not_raise_and_do_not_leak(
    msg: str, args: tuple[object, ...]
) -> None:
    record = _record(msg, args)
    assert RedactingFilter().filter(record) is True
    out = record.getMessage()  # a handler calls this next; it must not raise either
    assert "9876543210" not in out
    assert out  # something useful is still logged


def test_broken_format_args_keep_the_message_template_and_mask_the_args() -> None:
    record = _record("user %d", ("abc test@example.com",))
    RedactingFilter().filter(record)
    assert record.getMessage().startswith("user %d")
    assert "[email]" in record.getMessage()


def test_broken_format_args_do_not_reach_the_handler_error_path(
    logged: tuple[logging.Logger, list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    log, lines = logged
    log.info("user %d", "abc 9876543210")
    assert len(lines) == 1
    assert "9876543210" not in lines[0]
    assert "Logging error" not in capsys.readouterr().err  # Handler.handleError stays silent


def test_unprintable_args_and_messages_do_not_raise() -> None:
    bad_arg = _record("value %s", (_Unprintable(),))
    assert RedactingFilter().filter(bad_arg) is True
    assert bad_arg.getMessage().startswith("value %s ")
    assert "<unprintable>" in bad_arg.getMessage()

    bad_msg = _record(_Unprintable(), ())
    assert RedactingFilter().filter(bad_msg) is True
    assert bad_msg.getMessage().startswith("<unprintable> ")


def test_a_failure_inside_redaction_withholds_the_message_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(text: str) -> str:
        raise RuntimeError("regex engine exploded")

    monkeypatch.setattr(redact_module, "redact", boom)
    record = _record("user %s", ("9876543210",), exc_info=(ValueError, ValueError("x"), None))
    assert RedactingFilter().filter(record) is True
    assert record.getMessage() == redact_module.WITHHELD_MESSAGE
    assert "9876543210" not in record.getMessage()
    assert record.exc_info is None
    assert record.exc_text is None
    assert record.stack_info is None


# --------------------------------------------------------------------------------------------
# install_redaction()
# --------------------------------------------------------------------------------------------


def _redacting_filters(handler: logging.Handler) -> list[logging.Filter]:
    return [f for f in handler.filters if isinstance(f, RedactingFilter)]


def test_install_attaches_one_filter_to_every_handler_of_the_given_logger() -> None:
    logger = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    handlers = [_ListHandler(), _ListHandler()]
    for handler in handlers:
        logger.addHandler(handler)
    install_redaction(logger)
    assert [len(_redacting_filters(h)) for h in handlers] == [1, 1]


def test_install_is_idempotent() -> None:
    logger = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    handler = _ListHandler()
    logger.addHandler(handler)
    for _ in range(3):
        install_redaction(logger)
    assert len(_redacting_filters(handler)) == 1


def test_install_covers_handlers_added_since_the_last_call() -> None:
    logger = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    first, second = _ListHandler(), _ListHandler()
    logger.addHandler(first)
    install_redaction(logger)
    logger.addHandler(second)
    install_redaction(logger)
    assert [len(_redacting_filters(h)) for h in (first, second)] == [1, 1]


def test_install_keeps_filters_the_handler_already_had() -> None:
    logger = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    handler = _ListHandler()
    other = logging.Filter("something")
    handler.addFilter(other)
    logger.addHandler(handler)
    install_redaction(logger)
    assert other in handler.filters
    assert len(_redacting_filters(handler)) == 1


def test_install_on_a_logger_without_handlers_is_a_no_op() -> None:
    logger = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    install_redaction(logger)
    assert logger.handlers == []


def test_install_does_not_touch_other_loggers_handlers() -> None:
    mine = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    theirs = logging.getLogger(f"redact_test.{uuid.uuid4().hex}")
    my_handler, their_handler = _ListHandler(), _ListHandler()
    mine.addHandler(my_handler)
    theirs.addHandler(their_handler)
    install_redaction(mine)
    assert _redacting_filters(their_handler) == []


def test_install_defaults_to_the_root_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    handler = _ListHandler()
    monkeypatch.setattr(root, "handlers", [handler])  # restored after the test
    install_redaction()
    install_redaction()
    assert len(_redacting_filters(handler)) == 1

    # A logger far down the tree reaches the root handler, and is masked there.
    log = logging.getLogger(f"redact_test.{uuid.uuid4().hex}.deep.child")
    log.setLevel(logging.DEBUG)
    log.info("phone %s", "9876543210")
    assert handler.lines == ["INFO phone [phone]"]
