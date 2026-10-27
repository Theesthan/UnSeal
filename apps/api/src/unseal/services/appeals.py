"""First appeal service (FR-10, S. 19(1)): draft the appeal and record that it was filed.

No model call: every date, the filing mode and the grounds are code-owned template text, so the
letter cannot misstate a fact (a recorded appeal_facts run turned a postal filing into an email).
The appellant's own words (`details`, `delay_reason`) are printed as given. Dates come only from
the rules engine and the case record.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from unseal.db.models import Case, CaseStatus, DocumentKind
from unseal.harness.validate import Flag
from unseal.pdf.models import AppealDocument, Ground
from unseal.rules.deadlines import (
    Deadline,
    appeal_lateness,
    faa_decision_deadlines,
    first_appeal_deadline,
    second_appeal_deadline,
)
from unseal.rules.engine import load_rules
from unseal.services.cases import (
    Blocked,
    WrongStatus,
    _engine_deadlines,
    _put_deadline,
    _replace_document,
    _transition,
    check,
    today_ist,
)

AppealRenderer = Callable[[AppealDocument], bytes]

_ANSWERED = {CaseStatus.REPLIED.value, CaseStatus.DEEMED_REFUSED.value}
# What the appeal letter itself needs: the respondent PIO and the appellant (not the questions,
# since a case filed outside UnSeal may have none).
_APPEAL_BLOCKS = {"missing_pio_address", "missing_applicant_address"}


class InvalidGrounds(Exception):
    """A ground that cannot apply to this case (no_reply after a reply arrived)."""


class AppealInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grounds: list[Ground] = Field(min_length=1)
    faa_address: str = Field(min_length=1, max_length=1000)
    details: str = Field("", max_length=2000)
    delay_reason: str = Field("", max_length=1000)
    place: str = Field("", max_length=100)

    @field_validator("grounds")
    @classmethod
    def _unique(cls, grounds: list[Ground]) -> list[Ground]:
        if len(set(grounds)) != len(grounds):
            raise ValueError("a ground is repeated")
        return grounds


class AppealFiling(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filed_on: date
    received_on: date | None = None


def _pio_reply(case: Case) -> Deadline:
    pio_reply: Deadline = _engine_deadlines(case, case.received_on).pio_reply
    return pio_reply


def _appealable(case: Case, today: date) -> set[str]:
    """Statuses an appeal may start from. A reply_due case whose PIO day has passed is a deemed
    refusal already (S. 7(2)), even before the nightly job flips its status."""
    if case.status == CaseStatus.REPLY_DUE.value and _pio_reply(case).due_on < today:
        return _ANSWERED | {CaseStatus.REPLY_DUE.value}
    return _ANSWERED


async def build_first_appeal(
    session: AsyncSession,
    case: Case,
    renderer: AppealRenderer,
    storage_dir: Path,
    data: AppealInput,
) -> bytes:
    today = today_ist()
    if case.status not in _appealable(case, today) | {CaseStatus.APPEALED.value}:
        raise WrongStatus
    if "no_reply" in data.grounds and case.reply_received_on is not None:
        raise InvalidGrounds
    blocking = [f for f in check(case) if f.severity == "block" and f.code in _APPEAL_BLOCKS]
    if not (case.authority_name or "").strip() and not blocking:  # the PIO block is incomplete
        blocking = [Flag(code="missing_pio_address", severity="block")]
    if blocking or case.applicant is None:
        raise Blocked(blocking)
    rules = load_rules(case.jurisdiction)
    pio_reply = _pio_reply(case)
    window = first_appeal_deadline(pio_reply, rules=rules, reply_received_on=case.reply_received_on)
    lateness = appeal_lateness(window, case.appeal_filed_on or today, rules=rules)
    document = AppealDocument(
        language=case.language,
        jurisdiction=case.jurisdiction,
        authority_name=case.authority_name or "",
        pio_address=case.pio_address or "",
        faa_address=data.faa_address,
        appellant_name=case.applicant.name,
        appellant_address=case.applicant.address or "",
        filed_on=case.filed_on,
        filing_mode=case.filing_mode,
        received_on=case.received_on,
        received_estimated=case.received_estimated,
        reply_due_on=pio_reply.due_on,
        reply_received_on=case.reply_received_on,
        grounds=data.grounds,
        details=data.details,
        late=lateness.late,
        delay_reason=data.delay_reason,
        prepared_on=today,
        place=data.place,
    )
    pdf = await run_in_threadpool(renderer, document)  # WeasyPrint is CPU-bound
    await _replace_document(session, case, storage_dir, pdf, DocumentKind.FIRST_APPEAL)
    return pdf


async def file_first_appeal(session: AsyncSession, case: Case, data: AppealFiling) -> None:
    """The appeal went in: start the FAA's S. 19(6) clock and the S. 19(3) second-appeal window
    that follows it."""
    await _transition(
        session,
        case,
        _appealable(case, today_ist()),
        status=CaseStatus.APPEALED.value,
        appeal_filed_on=data.filed_on,
    )
    case.appeal_filed_on = data.filed_on
    rules = load_rules(case.jurisdiction)
    faa = faa_decision_deadlines(
        rules=rules, appeal_filed_on=data.filed_on, appeal_received_on=data.received_on
    )
    second = second_appeal_deadline(faa, rules=rules)
    for deadline in (faa.decision, second):
        _put_deadline(session, case, deadline.kind, deadline.due_on, deadline.estimated)
    await session.commit()
