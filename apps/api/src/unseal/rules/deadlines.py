"""Statutory deadlines: pure functions over the rules engine (golden rule 1).

Every day or hour count is read from `Rules` (rules/data/rti_act.json); this module holds no legal
number (a test scans it). The one literal is the transit buffer, an app setting (CLAUDE.md), not
law. No I/O, no clock reads: callers pass every anchor date in.

Conventions (CLAUDE.md, "Date math conventions"):
- Calendar days. The day of receipt is day 0, so `due_on = received_on + timedelta(days=N)`, and
  `due_on` is the last day still in time: filing on it is in time, the day after is late.
- Dates are `date` values in Asia/Kolkata. The 48-hour track also returns `due_at`, a UTC
  timestamp, whenever the receipt timestamp is known; the hours are elapsed hours.
- Unknown receipt: `filed_on + transit_buffer_days`, and every date resting on it carries
  `estimated=True`. An actual receipt date clears it.

How the reply periods combine (`pio_reply_period`; legal readings to confirm):
- Assistant PIO and third party: 40 days, not 45. Section 5(2) adds five days "in computing the
  period for response specified under sub-section (1) of section 7"; the 40 days come from
  s. 11(3), which applies "notwithstanding anything contained in section 7", so it replaces the
  s. 7(1) period and the five days do not attach to it. It is also the earlier date, which opens
  the user's first-appeal window sooner (conservative).
- Assistant PIO and life or liberty: 48 hours plus five days. The 48 hours are the proviso to
  s. 7(1), so they are "the period ... under sub-section (1) of section 7"; DoPT guidance reads
  it the same way ("48 hours plus 5 days").
- Life or liberty and third party: 48 hours. The Act does not say how the urgent proviso and
  s. 11(3) meet; the earlier date keeps the user's appeal clock conservative.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict

from unseal.rules.engine import Appeal, Rules

TRANSIT_BUFFER_DAYS: Final = 7  # posting to receipt; app setting (CLAUDE.md), not law
IST: Final = ZoneInfo("Asia/Kolkata")

DeadlineKind = Literal[
    # The PRD `deadlines.kind` values: the user's clock, stored and reminded.
    "pio_reply",
    "first_appeal",
    "faa_decision",
    "second_appeal",
    # Informational: shown on the timeline, never an appeal anchor.
    "faa_decision_extended",  # s. 19(6) outer limit
    "transfer",  # s. 6(3): the first PIO must transfer by this date
    "new_authority_reply",  # expected reply after a transfer (DoPT guidance, not statute)
]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Deadline(_Frozen):
    kind: DeadlineKind
    due_on: date  # last day still in time, Asia/Kolkata
    estimated: bool  # rests on an assumed receipt date (filed_on + transit buffer)
    basis: tuple[str, ...]  # the rules the date comes from, e.g. "RTI Act 2005, s. 7(1)"
    due_at: AwareDatetime | None = None  # 48-hour track only, UTC, when the receipt time is known


class CaseDeadlines(_Frozen):
    """What `compute_deadlines` returns: every due date known at filing."""

    received_on: date  # day 0: the actual receipt, or filed_on + transit buffer
    received_estimated: bool
    pio_reply: Deadline
    first_appeal: Deadline  # deemed-refusal window; recompute with the reply date once it comes


class FaaDeadlines(_Frozen):
    decision: Deadline  # kind faa_decision: days from receipt of the first appeal
    extended_limit: Deadline  # kind faa_decision_extended: max_days from its filing


class TransferDeadlines(_Frozen):
    transfer_due: Deadline
    new_authority_reply: Deadline  # informational only
    first_appeal_on_original_receipt: Deadline  # unchanged by the transfer


class Lateness(_Frozen):
    late: bool
    days_late: int
    late_allowed: bool  # the authority may still admit it for sufficient cause


def pio_reply_period(
    *, rules: Rules, via_apio: bool, third_party: bool, life_liberty: bool
) -> timedelta:
    """Time the PIO has from receipt. How the cases combine: see the module docstring."""
    period, _ = _reply_terms(
        rules, via_apio=via_apio, third_party=third_party, life_liberty=life_liberty
    )
    return period


def compute_deadlines(
    *,
    filed_on: date,
    received_on: date | None,
    via_apio: bool,
    third_party: bool,
    life_liberty: bool,
    rules: Rules,
    received_at: datetime | None = None,
    transit_buffer_days: int = TRANSIT_BUFFER_DAYS,
) -> CaseDeadlines:
    """The PRD function tool: every due date known at filing, each marked exact or estimated.

    `received_on` is the day the PIO (or the Assistant PIO, when `via_apio`) received it.
    `received_at`, a timezone-aware receipt timestamp, gives the 48-hour track its `due_at`;
    without it the life-or-liberty deadline is a date only. The first appeal is the
    deemed-refusal window (s. 7(2)); FAA and second-appeal dates need the first appeal itself,
    so `faa_decision_deadlines` and `second_appeal_deadline` compute them later.
    """
    known_on = _receipt_day(received_at, received_on)
    day0, estimated = _receipt(filed_on, known_on, transit_buffer_days)
    period, basis = _reply_terms(
        rules, via_apio=via_apio, third_party=third_party, life_liberty=life_liberty
    )
    due_at = None
    due_on = day0 + period  # drops any part of a day; exact for the 48 hours (two whole days)
    if life_liberty and received_at is not None:
        due_at = received_at.astimezone(UTC) + period  # elapsed hours, whatever the input zone
        due_on = due_at.astimezone(IST).date()
    pio_reply = Deadline(
        kind="pio_reply", due_on=due_on, estimated=estimated, basis=basis, due_at=due_at
    )
    return CaseDeadlines(
        received_on=day0,
        received_estimated=estimated,
        pio_reply=pio_reply,
        first_appeal=first_appeal_deadline(pio_reply, rules=rules),
    )


def first_appeal_deadline(
    pio_reply: Deadline, *, rules: Rules, reply_received_on: date | None = None
) -> Deadline:
    """S. 19(1): `first_appeal.days` from the reply's receipt, or, with no reply, from the
    expiry of the PIO's period (deemed refusal, s. 7(2)).

    A reply that arrives counts from its own receipt, even if late: the user is then "aggrieved
    by a decision" and s. 19(1) runs "from the receipt of such a decision". Only an original
    `pio_reply` can anchor this clock, never a transferred authority's expected reply.
    """
    if pio_reply.kind != "pio_reply":
        raise ValueError(f"the first appeal runs from a pio_reply deadline, not {pio_reply.kind}")
    appeal = rules.act.first_appeal
    window = timedelta(days=appeal.days)
    if reply_received_on is not None:
        return Deadline(
            kind="first_appeal",
            due_on=reply_received_on + window,
            estimated=False,
            basis=(appeal.basis,),
        )
    return Deadline(
        kind="first_appeal",
        due_on=pio_reply.due_on + window,
        estimated=pio_reply.estimated,
        basis=(rules.act.deemed_refusal.basis, appeal.basis),
    )


def faa_decision_deadlines(
    *,
    rules: Rules,
    appeal_filed_on: date,
    appeal_received_on: date | None = None,
    transit_buffer_days: int = TRANSIT_BUFFER_DAYS,
) -> FaaDeadlines:
    """S. 19(6): decided within `faa_decision.days` of the appeal's receipt, extendable to a
    total of `max_days` from its filing.

    The outer limit counts from filing, so it is exact even when receipt is estimated. If the
    appeal arrived so late that the normal date already passes the outer limit, there is no
    room to extend and the outer limit equals the normal date (never earlier than it).
    """
    faa = rules.act.faa_decision
    received, estimated = _receipt(appeal_filed_on, appeal_received_on, transit_buffer_days)
    decision = Deadline(
        kind="faa_decision",
        due_on=received + timedelta(days=faa.days),
        estimated=estimated,
        basis=(faa.basis,),
    )
    outer_on = appeal_filed_on + timedelta(days=faa.max_days)
    no_room = decision.due_on > outer_on
    extended = Deadline(
        kind="faa_decision_extended",
        due_on=decision.due_on if no_room else outer_on,
        estimated=decision.estimated and no_room,
        basis=(faa.basis,),
    )
    return FaaDeadlines(decision=decision, extended_limit=extended)


def second_appeal_deadline(
    faa: FaaDeadlines,
    *,
    rules: Rules,
    decision_received_on: date | None = None,
    faa_extended: bool = False,
) -> Deadline:
    """S. 19(3): `second_appeal.days` from the day the FAA decision was received, or, with no
    decision, from the day it should have been made.

    That day is the normal FAA date unless the authority recorded an extension
    (`faa_extended`), which moves it to the outer limit. Defaulting to the normal date gives the
    earlier, conservative second-appeal date.
    """
    appeal = rules.act.second_appeal
    window = timedelta(days=appeal.days)
    if decision_received_on is not None:
        return Deadline(
            kind="second_appeal",
            due_on=decision_received_on + window,
            estimated=False,
            basis=(appeal.basis,),
        )
    anchor = faa.extended_limit if faa_extended else faa.decision
    return Deadline(
        kind="second_appeal",
        due_on=anchor.due_on + window,
        estimated=anchor.estimated,
        basis=(rules.act.faa_decision.basis, appeal.basis),
    )


def transfer_deadlines(
    original: CaseDeadlines,
    *,
    rules: Rules,
    new_received_on: date | None = None,
    transferred_on: date | None = None,
    third_party: bool = False,
    life_liberty: bool = False,
    transit_buffer_days: int = TRANSIT_BUFFER_DAYS,
) -> TransferDeadlines:
    """S. 6(3) proviso: the first PIO must transfer within `transfer.days` of its receipt.

    The Act is silent on when the new authority's period runs; the DoPT Guide says from the new
    authority's receipt. That date is returned as informational only: the user's first-appeal
    clock stays on the ORIGINAL receipt (the conservative default in rti_act.json). The new
    authority gets no Assistant PIO days (a transfer goes PIO to PIO). With its receipt unknown,
    it is estimated from the transfer letter's date, or else from the last lawful transfer day,
    plus the transit buffer.
    """
    transfer = rules.act.transfer
    transfer_due = Deadline(
        kind="transfer",
        due_on=original.received_on + timedelta(days=transfer.days),
        estimated=original.received_estimated,
        basis=(transfer.basis,),
    )
    if new_received_on is not None:
        new_day0, estimated = new_received_on, False
    else:
        sent_on = transferred_on if transferred_on is not None else transfer_due.due_on
        new_day0, estimated = _receipt(sent_on, None, transit_buffer_days)
    period, basis = _reply_terms(
        rules, via_apio=False, third_party=third_party, life_liberty=life_liberty
    )
    expected = Deadline(
        kind="new_authority_reply",
        due_on=new_day0 + period,
        estimated=estimated,
        basis=(transfer.basis, *basis),
    )
    return TransferDeadlines(
        transfer_due=transfer_due,
        new_authority_reply=expected,
        first_appeal_on_original_receipt=original.first_appeal,
    )


def appeal_lateness(deadline: Deadline, filed_on: date, *, rules: Rules) -> Lateness:
    """Whether an appeal filed on `filed_on` is late. A late appeal is still draftable: the
    authority may admit it for sufficient cause (`late_allowed`), so this reports, never refuses.
    """
    appeal = _appeal_rule(deadline.kind, rules)
    days_late = max((filed_on - deadline.due_on).days, 0)
    return Lateness(late=days_late > 0, days_late=days_late, late_allowed=appeal.late_allowed)


def _reply_terms(
    rules: Rules, *, via_apio: bool, third_party: bool, life_liberty: bool
) -> tuple[timedelta, tuple[str, ...]]:
    act = rules.act
    if third_party and not life_liberty:
        # s. 11(3) applies notwithstanding s. 7: it replaces the s. 7(1) period, no APIO days.
        return timedelta(days=act.third_party_reply.days), (act.third_party_reply.basis,)
    if life_liberty:
        period, basis = timedelta(hours=act.life_liberty_reply.hours), act.life_liberty_reply.basis
    else:
        period, basis = timedelta(days=act.pio_reply.days), act.pio_reply.basis
    if via_apio:
        return period + timedelta(days=act.apio_extra.days), (basis, act.apio_extra.basis)
    return period, (basis,)


def _receipt(filed_on: date, received_on: date | None, buffer_days: int) -> tuple[date, bool]:
    """Day 0 and whether it is estimated."""
    if buffer_days < 0:
        raise ValueError("transit_buffer_days must not be negative")
    if received_on is None:
        return filed_on + timedelta(days=buffer_days), True
    if received_on < filed_on:
        raise ValueError(f"received on {received_on} is before filing on {filed_on}")
    return received_on, False


def _receipt_day(received_at: datetime | None, received_on: date | None) -> date | None:
    """The Asia/Kolkata receipt date, taken from the timestamp when there is one."""
    if received_at is None:
        return received_on
    if received_at.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")
    day = received_at.astimezone(IST).date()
    if received_on is not None and received_on != day:
        raise ValueError(f"received_at falls on {day} in Asia/Kolkata, a different day")
    return day


def _appeal_rule(kind: DeadlineKind, rules: Rules) -> Appeal:
    if kind == "first_appeal":
        return rules.act.first_appeal
    if kind == "second_appeal":
        return rules.act.second_appeal
    raise ValueError(f"not an appeal deadline: {kind}")
