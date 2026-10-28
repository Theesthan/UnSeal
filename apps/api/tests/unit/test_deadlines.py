"""Statutory deadline engine. Every count comes from the rules data; the day of receipt is day 0,
so `due_on = received_on + timedelta(days=N)` and `due_on` is the last day still in time.

The literal day counts below pin the researched values on purpose: a JSON or engine change that
moves a statutory date must fail here."""

import io
import tokenize
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import get_args
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from unseal.rules import deadlines
from unseal.rules.deadlines import (
    IST,
    TRANSIT_BUFFER_DAYS,
    CaseDeadlines,
    Deadline,
    DeadlineKind,
    FaaDeadlines,
    Lateness,
    appeal_lateness,
    compute_deadlines,
    faa_decision_deadlines,
    first_appeal_deadline,
    pio_reply_period,
    second_appeal_deadline,
    transfer_deadlines,
)
from unseal.rules.engine import Rules, load_rules

FILED = date(2026, 1, 5)
RECEIVED = date(2026, 1, 7)


@pytest.fixture(scope="module")
def rules() -> Rules:
    return load_rules("central")


def case(
    rules: Rules,
    *,
    filed_on: date = FILED,
    received_on: date | None = None,
    via_apio: bool = False,
    third_party: bool = False,
    life_liberty: bool = False,
    received_at: datetime | None = None,
    transit_buffer_days: int = TRANSIT_BUFFER_DAYS,
) -> CaseDeadlines:
    return compute_deadlines(
        filed_on=filed_on,
        received_on=received_on,
        via_apio=via_apio,
        third_party=third_party,
        life_liberty=life_liberty,
        rules=rules,
        received_at=received_at,
        transit_buffer_days=transit_buffer_days,
    )


def faa_from_known_receipt(rules: Rules) -> FaaDeadlines:
    return faa_decision_deadlines(
        rules=rules, appeal_filed_on=date(2026, 3, 2), appeal_received_on=date(2026, 3, 5)
    )


# PIO reply period: 30, 35, 40 days and 48 hours ---------------------------------------------


@pytest.mark.parametrize(
    ("via_apio", "third_party", "life_liberty", "expected"),
    [
        (False, False, False, timedelta(days=30)),  # s. 7(1)
        (True, False, False, timedelta(days=35)),  # s. 5(2) proviso: 5 days added
        (False, True, False, timedelta(days=40)),  # s. 11(3)
        (True, True, False, timedelta(days=40)),  # APIO days not added to the s. 11(3) period
        (False, False, True, timedelta(hours=48)),  # s. 7(1) proviso
        (True, False, True, timedelta(hours=48) + timedelta(days=5)),  # added to 48 hours too
        (False, True, True, timedelta(hours=48)),  # life or liberty keeps 48 hours
        (True, True, True, timedelta(hours=48) + timedelta(days=5)),
    ],
)
def test_pio_reply_period(
    rules: Rules, via_apio: bool, third_party: bool, life_liberty: bool, expected: timedelta
) -> None:
    period = pio_reply_period(
        rules=rules, via_apio=via_apio, third_party=third_party, life_liberty=life_liberty
    )
    assert period == expected


def test_pio_reply_is_30_days_from_receipt(rules: Rules) -> None:
    result = case(rules, received_on=RECEIVED)
    assert result.received_on == RECEIVED
    assert result.received_estimated is False
    assert result.pio_reply == Deadline(
        kind="pio_reply",
        due_on=date(2026, 2, 6),
        estimated=False,
        basis=(rules.act.pio_reply.basis,),
    )


def test_receipt_on_the_filing_day_is_day_zero(rules: Rules) -> None:
    result = case(rules, filed_on=RECEIVED, received_on=RECEIVED)
    assert result.pio_reply.due_on == date(2026, 2, 6)


def test_apio_adds_five_days(rules: Rules) -> None:
    reply = case(rules, received_on=RECEIVED, via_apio=True).pio_reply
    assert reply.due_on == date(2026, 2, 11)
    assert reply.basis == (rules.act.pio_reply.basis, rules.act.apio_extra.basis)


def test_third_party_is_40_days(rules: Rules) -> None:
    reply = case(rules, received_on=RECEIVED, third_party=True).pio_reply
    assert reply.due_on == date(2026, 2, 16)
    assert reply.basis == (rules.act.third_party_reply.basis,)


def test_apio_with_third_party_stays_40_days(rules: Rules) -> None:
    reply = case(rules, received_on=RECEIVED, via_apio=True, third_party=True).pio_reply
    assert reply.due_on == date(2026, 2, 16)
    assert reply.basis == (rules.act.third_party_reply.basis,)


# Calendar boundaries ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("received_on", "due_on"),
    [
        (date(2026, 1, 31), date(2026, 3, 2)),  # month end; February 2026 has 28 days
        (date(2026, 12, 15), date(2027, 1, 14)),  # year end
        (date(2028, 2, 29), date(2028, 3, 30)),  # leap day as the receipt date
        (date(2028, 1, 30), date(2028, 2, 29)),  # leap day as the due date
    ],
)
def test_calendar_boundaries(rules: Rules, received_on: date, due_on: date) -> None:
    result = case(rules, filed_on=received_on, received_on=received_on)
    assert result.pio_reply.due_on == due_on


@pytest.mark.parametrize(
    ("received_on", "via_apio", "third_party"),
    [
        (date(2028, 1, 25), True, False),  # 35 days
        (date(2028, 1, 20), False, True),  # 40 days
    ],
)
def test_leap_day_as_the_35_and_40_day_due_date(
    rules: Rules, received_on: date, via_apio: bool, third_party: bool
) -> None:
    result = case(
        rules,
        filed_on=received_on,
        received_on=received_on,
        via_apio=via_apio,
        third_party=third_party,
    )
    assert result.pio_reply.due_on == date(2028, 2, 29)


# Life or liberty: 48 hours on timestamps -------------------------------------------------------


def test_48_hours_across_midnight(rules: Rules) -> None:
    received_at = datetime(2026, 3, 10, 23, 30, tzinfo=IST)
    result = case(rules, filed_on=date(2026, 3, 10), life_liberty=True, received_at=received_at)
    reply = result.pio_reply
    assert reply.due_at == datetime(2026, 3, 12, 18, 0, tzinfo=UTC)
    assert reply.due_at is not None and reply.due_at.utcoffset() == timedelta(0)
    assert reply.due_on == date(2026, 3, 12)
    assert reply.estimated is False
    assert reply.basis == (rules.act.life_liberty_reply.basis,)
    assert result.received_on == date(2026, 3, 10)


def test_48_hours_use_the_ist_date_not_the_utc_date(rules: Rules) -> None:
    # 02:00 IST on 10 March is 20:30 UTC on 9 March.
    received_at = datetime(2026, 3, 10, 2, 0, tzinfo=IST)
    result = case(rules, filed_on=date(2026, 3, 9), life_liberty=True, received_at=received_at)
    assert result.received_on == date(2026, 3, 10)
    assert result.pio_reply.due_at == datetime(2026, 3, 11, 20, 30, tzinfo=UTC)
    assert result.pio_reply.due_on == date(2026, 3, 12)  # the UTC date would be 11 March
    assert result.first_appeal.due_on == date(2026, 4, 11)


def test_48_hours_from_a_utc_timestamp_match_the_ist_one(rules: Rules) -> None:
    in_ist = case(
        rules,
        filed_on=date(2026, 3, 9),
        life_liberty=True,
        received_at=datetime(2026, 3, 10, 2, 0, tzinfo=IST),
    )
    in_utc = case(
        rules,
        filed_on=date(2026, 3, 9),
        life_liberty=True,
        received_at=datetime(2026, 3, 9, 20, 30, tzinfo=UTC),
    )
    assert in_utc == in_ist


def test_48_hours_are_elapsed_hours_across_a_dst_change(rules: Rules) -> None:
    # Europe/London moves to summer time at 01:00 UTC on 29 March 2026; 48 hours stay 48 hours.
    received_at = datetime(2026, 3, 28, 12, 0, tzinfo=ZoneInfo("Europe/London"))
    result = case(rules, filed_on=date(2026, 3, 28), life_liberty=True, received_at=received_at)
    assert result.pio_reply.due_at == datetime(2026, 3, 30, 12, 0, tzinfo=UTC)


def test_48_hours_via_apio_add_five_days(rules: Rules) -> None:
    received_at = datetime(2026, 3, 10, 9, 0, tzinfo=IST)
    result = case(
        rules,
        filed_on=date(2026, 3, 10),
        via_apio=True,
        life_liberty=True,
        received_at=received_at,
    )
    assert result.pio_reply.due_at == datetime(2026, 3, 17, 3, 30, tzinfo=UTC)  # 09:00 IST
    assert result.pio_reply.due_on == date(2026, 3, 17)


def test_48_hours_without_a_receipt_time_give_the_date_only(rules: Rules) -> None:
    reply = case(
        rules, filed_on=date(2026, 3, 10), received_on=date(2026, 3, 10), life_liberty=True
    ).pio_reply
    assert reply.due_on == date(2026, 3, 12)
    assert reply.due_at is None
    assert reply.estimated is False


def test_a_receipt_timestamp_sets_the_date_on_the_day_track(rules: Rules) -> None:
    received_at = datetime(2026, 3, 10, 2, 0, tzinfo=IST)
    result = case(rules, filed_on=date(2026, 3, 9), received_at=received_at)
    assert result.received_on == date(2026, 3, 10)
    assert result.pio_reply.due_on == date(2026, 4, 9)
    assert result.pio_reply.due_at is None


def test_a_naive_receipt_timestamp_is_rejected(rules: Rules) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        case(rules, life_liberty=True, received_at=datetime(2026, 3, 10, 9, 0))


def test_a_receipt_timestamp_must_match_the_receipt_date(rules: Rules) -> None:
    with pytest.raises(ValueError, match="different"):
        case(
            rules,
            filed_on=date(2026, 3, 9),
            received_on=date(2026, 3, 9),
            life_liberty=True,
            received_at=datetime(2026, 3, 10, 2, 0, tzinfo=IST),
        )


# Estimated receipt ------------------------------------------------------------------------------


def test_unknown_receipt_uses_the_transit_buffer_and_is_estimated(rules: Rules) -> None:
    result = case(rules)
    assert TRANSIT_BUFFER_DAYS == 7
    assert result.received_on == date(2026, 1, 12)
    assert result.received_estimated is True
    assert result.pio_reply.due_on == date(2026, 2, 11)
    assert result.pio_reply.estimated is True
    assert result.first_appeal.estimated is True


def test_an_actual_receipt_date_clears_estimated(rules: Rules) -> None:
    assert case(rules).pio_reply.estimated is True
    actual = case(rules, received_on=date(2026, 1, 9))
    assert actual.received_estimated is False
    assert actual.pio_reply.estimated is False
    assert actual.first_appeal.estimated is False
    assert actual.pio_reply.due_on == date(2026, 2, 8)


def test_the_transit_buffer_is_configurable(rules: Rules) -> None:
    assert case(rules, transit_buffer_days=3).received_on == date(2026, 1, 8)


def test_life_liberty_with_unknown_receipt_is_estimated(rules: Rules) -> None:
    reply = case(rules, filed_on=date(2026, 3, 10), life_liberty=True).pio_reply
    assert reply.due_on == date(2026, 3, 19)
    assert reply.estimated is True
    assert reply.due_at is None


def test_a_negative_transit_buffer_is_rejected(rules: Rules) -> None:
    with pytest.raises(ValueError, match="transit_buffer_days"):
        case(rules, transit_buffer_days=-1)


def test_receipt_before_filing_is_rejected(rules: Rules) -> None:
    with pytest.raises(ValueError, match="before"):
        case(rules, received_on=date(2026, 1, 4))


# First appeal (s. 19(1)) -------------------------------------------------------------------------


def test_first_appeal_from_deemed_refusal(rules: Rules) -> None:
    result = case(rules, received_on=RECEIVED)
    assert result.first_appeal == Deadline(
        kind="first_appeal",
        due_on=date(2026, 3, 8),
        estimated=False,
        basis=(rules.act.deemed_refusal.basis, rules.act.first_appeal.basis),
    )


def test_first_appeal_from_the_reply_date(rules: Rules) -> None:
    estimated_reply = case(rules).pio_reply
    appeal = first_appeal_deadline(estimated_reply, rules=rules, reply_received_on=date(2026, 2, 1))
    assert appeal == Deadline(
        kind="first_appeal",
        due_on=date(2026, 3, 3),
        estimated=False,
        basis=(rules.act.first_appeal.basis,),
    )


def test_first_appeal_needs_a_pio_reply_deadline(rules: Rules) -> None:
    result = case(rules, received_on=RECEIVED)
    with pytest.raises(ValueError, match="pio_reply"):
        first_appeal_deadline(result.first_appeal, rules=rules)


def test_first_appeal_on_the_due_date_is_in_time_and_a_day_later_is_late(rules: Rules) -> None:
    appeal = case(rules, received_on=RECEIVED).first_appeal  # due 8 March
    assert appeal_lateness(appeal, date(2026, 3, 8), rules=rules) == Lateness(
        late=False, days_late=0, late_allowed=True
    )
    assert appeal_lateness(appeal, date(2026, 3, 9), rules=rules) == Lateness(
        late=True, days_late=1, late_allowed=True
    )
    assert appeal_lateness(appeal, date(2026, 2, 1), rules=rules).late is False


def test_second_appeal_lateness(rules: Rules) -> None:
    appeal = second_appeal_deadline(faa_from_known_receipt(rules), rules=rules)  # due 3 July
    assert appeal_lateness(appeal, date(2026, 7, 13), rules=rules) == Lateness(
        late=True, days_late=10, late_allowed=True
    )


def test_lateness_reads_late_allowed_from_the_rules(rules: Rules) -> None:
    act = rules.act
    strict = rules.model_copy(
        update={
            "act": act.model_copy(
                update={"first_appeal": act.first_appeal.model_copy(update={"late_allowed": False})}
            )
        }
    )
    appeal = case(strict, received_on=RECEIVED).first_appeal
    assert appeal_lateness(appeal, date(2026, 3, 9), rules=strict).late_allowed is False


def test_lateness_is_only_for_appeals(rules: Rules) -> None:
    reply = case(rules, received_on=RECEIVED).pio_reply
    with pytest.raises(ValueError, match="pio_reply"):
        appeal_lateness(reply, date(2026, 3, 9), rules=rules)


# First appellate authority decision (s. 19(6)) ----------------------------------------------------


def test_faa_decision_is_30_days_from_receipt_and_at_most_45_from_filing(rules: Rules) -> None:
    faa = faa_from_known_receipt(rules)
    basis = (rules.act.faa_decision.basis,)
    assert faa.decision == Deadline(
        kind="faa_decision", due_on=date(2026, 4, 4), estimated=False, basis=basis
    )
    assert faa.extended_limit == Deadline(
        kind="faa_decision_extended", due_on=date(2026, 4, 16), estimated=False, basis=basis
    )


def test_faa_with_unknown_appeal_receipt(rules: Rules) -> None:
    faa = faa_decision_deadlines(rules=rules, appeal_filed_on=date(2026, 3, 2))
    assert faa.decision.due_on == date(2026, 4, 8)
    assert faa.decision.estimated is True
    assert faa.extended_limit.due_on == date(2026, 4, 16)  # counted from filing: exact
    assert faa.extended_limit.estimated is False


@pytest.mark.parametrize(
    ("appeal_received_on", "transit_buffer_days", "estimated"),
    [
        (date(2026, 3, 22), TRANSIT_BUFFER_DAYS, False),  # arrived 20 days after filing
        (None, 20, True),
    ],
)
def test_faa_outer_limit_is_never_before_the_normal_date(
    rules: Rules, appeal_received_on: date | None, transit_buffer_days: int, estimated: bool
) -> None:
    faa = faa_decision_deadlines(
        rules=rules,
        appeal_filed_on=date(2026, 3, 2),
        appeal_received_on=appeal_received_on,
        transit_buffer_days=transit_buffer_days,
    )
    assert faa.decision.due_on == date(2026, 4, 21)
    assert faa.extended_limit.due_on == date(2026, 4, 21)
    assert faa.extended_limit.estimated is estimated


def test_faa_appeal_received_before_filing_is_rejected(rules: Rules) -> None:
    with pytest.raises(ValueError, match="before"):
        faa_decision_deadlines(
            rules=rules, appeal_filed_on=date(2026, 3, 2), appeal_received_on=date(2026, 3, 1)
        )


# Second appeal (s. 19(3)) -------------------------------------------------------------------------


def test_second_appeal_is_90_days_from_the_decision(rules: Rules) -> None:
    appeal = second_appeal_deadline(
        faa_from_known_receipt(rules), rules=rules, decision_received_on=date(2026, 4, 10)
    )
    assert appeal == Deadline(
        kind="second_appeal",
        due_on=date(2026, 7, 9),
        estimated=False,
        basis=(rules.act.second_appeal.basis,),
    )


def test_second_appeal_from_the_faa_deadline_when_no_decision_came(rules: Rules) -> None:
    appeal = second_appeal_deadline(faa_from_known_receipt(rules), rules=rules)
    assert appeal.due_on == date(2026, 7, 3)
    assert appeal.estimated is False
    assert appeal.basis == (rules.act.faa_decision.basis, rules.act.second_appeal.basis)


def test_second_appeal_from_the_extended_faa_deadline(rules: Rules) -> None:
    appeal = second_appeal_deadline(faa_from_known_receipt(rules), rules=rules, faa_extended=True)
    assert appeal.due_on == date(2026, 7, 15)


def test_second_appeal_from_an_estimated_faa_deadline_is_estimated(rules: Rules) -> None:
    faa = faa_decision_deadlines(rules=rules, appeal_filed_on=date(2026, 3, 2))
    appeal = second_appeal_deadline(faa, rules=rules)
    assert appeal.due_on == date(2026, 7, 7)
    assert appeal.estimated is True


# Transfer (s. 6(3)) -------------------------------------------------------------------------------


def test_transfer_keeps_the_first_appeal_clock_on_the_original_receipt(rules: Rules) -> None:
    original = case(rules, received_on=RECEIVED)
    moved = transfer_deadlines(original, rules=rules, new_received_on=date(2026, 1, 15))
    act = rules.act
    assert moved.transfer_due == Deadline(
        kind="transfer", due_on=date(2026, 1, 12), estimated=False, basis=(act.transfer.basis,)
    )
    assert moved.new_authority_reply == Deadline(
        kind="new_authority_reply",
        due_on=date(2026, 2, 14),
        estimated=False,
        basis=(act.transfer.basis, act.pio_reply.basis),
    )
    assert moved.first_appeal_on_original_receipt == original.first_appeal
    assert moved.first_appeal_on_original_receipt.due_on == date(2026, 3, 8)  # not 16 March
    with pytest.raises(ValueError, match="pio_reply"):
        first_appeal_deadline(moved.new_authority_reply, rules=rules)


def test_transfer_with_unknown_new_receipt_is_estimated(rules: Rules) -> None:
    original = case(rules, received_on=RECEIVED)
    from_letter = transfer_deadlines(original, rules=rules, transferred_on=date(2026, 1, 10))
    assert from_letter.new_authority_reply.due_on == date(2026, 2, 16)
    assert from_letter.new_authority_reply.estimated is True
    latest = transfer_deadlines(original, rules=rules)  # assume the last lawful transfer day
    assert latest.new_authority_reply.due_on == date(2026, 2, 18)
    assert latest.new_authority_reply.estimated is True


def test_transfer_due_is_estimated_when_the_original_receipt_is(rules: Rules) -> None:
    moved = transfer_deadlines(case(rules), rules=rules, new_received_on=date(2026, 1, 20))
    assert moved.transfer_due.due_on == date(2026, 1, 17)
    assert moved.transfer_due.estimated is True
    assert moved.new_authority_reply.estimated is False


@pytest.mark.parametrize(
    ("third_party", "life_liberty", "due_on"),
    [(True, False, date(2026, 2, 24)), (False, True, date(2026, 1, 17))],
)
def test_transfer_expected_reply_follows_the_case_type(
    rules: Rules, third_party: bool, life_liberty: bool, due_on: date
) -> None:
    moved = transfer_deadlines(
        case(rules, received_on=RECEIVED),
        rules=rules,
        new_received_on=date(2026, 1, 15),
        third_party=third_party,
        life_liberty=life_liberty,
    )
    assert moved.new_authority_reply.due_on == due_on


# Values come from the rules, never from code ------------------------------------------------------


def test_every_count_comes_from_the_rules(rules: Rules) -> None:
    act = rules.act
    changed = rules.model_copy(
        update={
            "act": act.model_copy(
                update={
                    "pio_reply": act.pio_reply.model_copy(update={"days": 31}),
                    "first_appeal": act.first_appeal.model_copy(update={"days": 20}),
                }
            )
        }
    )
    result = case(changed, received_on=RECEIVED)
    assert result.pio_reply.due_on == date(2026, 2, 7)
    assert result.first_appeal.due_on == date(2026, 2, 27)


def numeric_literals(source: str) -> list[tuple[int, str]]:
    """(line, text) of every number in code; comments and strings (docstrings) are skipped."""
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return [(tok.start[0], tok.string) for tok in tokens if tok.type == tokenize.NUMBER]


def test_the_literal_scan_catches_a_hardcoded_deadline() -> None:
    snippet = '"""Due in 30 days."""\n# 48 hours\ndue = received + timedelta(days=30)\n'
    assert numeric_literals(snippet) == [(3, "30")]


def test_no_deadline_literal_in_the_engine() -> None:
    """Only 0 and the transit buffer default (an app setting) may be written as numbers."""
    source = Path(deadlines.__file__).read_text("utf-8")
    lines = source.splitlines()
    offending = [
        (line, text)
        for line, text in numeric_literals(source)
        if text != "0" and not lines[line - 1].startswith("TRANSIT_BUFFER_DAYS")
    ]
    assert offending == []


# Tool output --------------------------------------------------------------------------------------


def test_deadline_kinds_cover_the_prd_data_model() -> None:
    prd_kinds = {"pio_reply", "first_appeal", "faa_decision", "second_appeal"}
    assert prd_kinds <= set(get_args(DeadlineKind))


def test_results_are_frozen_and_round_trip_as_json(rules: Rules) -> None:
    result = case(
        rules,
        filed_on=date(2026, 3, 10),
        life_liberty=True,
        received_at=datetime(2026, 3, 10, 9, 0, tzinfo=IST),
    )
    assert CaseDeadlines.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        result.pio_reply.due_on = date(2026, 1, 1)  # type: ignore[misc]
