"""Case service: everything the routes and the Telegram bot do with a case (FR-2 to FR-8).

HTTP-agnostic on purpose: it raises NotFound or WrongStatus and the API maps them. Dates and
deadlines come only from the rules engine. Status changes are conditional updates, so a double
tap or a webhook redelivery cannot apply a transition twice (skill state-machine-feature).
"""

import json
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from unseal.db.models import (
    Applicant,
    Case,
    CaseStatus,
    Deadline,
    Document,
    DocumentKind,
    Question,
    User,
)
from unseal.harness.steps import StructuredLLM, compose, rewrite
from unseal.harness.validate import Draft, Flag, validate
from unseal.pdf.models import ApplicationDocument
from unseal.rules.deadlines import IST, compute_deadlines, first_appeal_deadline
from unseal.rules.engine import Jurisdiction, load_rules
from unseal.services.storage import remove_files, save


class NotFound(Exception):
    """The case or question does not exist for this user (same answer either way)."""


class WrongStatus(Exception):
    """The case is not in a status that allows this action."""


class Blocked(Exception):
    """Export is blocked by validator flags (FR-3: only missing mandatory fields block)."""

    def __init__(self, flags: list[Flag]) -> None:
        super().__init__("blocked")
        self.flags = flags


class InvalidDate(Exception):
    """A date that contradicts the case (for example a receipt before the filing)."""


class InvalidPaymentMode(Exception):
    """The payment mode is not one the jurisdiction's rules accept."""


class AuthorityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jurisdiction: Jurisdiction
    authority_name: str
    pio_address: str
    via_apio: bool = False
    third_party: bool = False
    life_liberty: bool = False


class ApplicantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    address: str
    phone: str | None = None
    bpl: bool = False


class FilingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filed_on: date
    filing_mode: Literal["rti_online", "post", "in_person"]
    received_on: date | None = None


def today_ist() -> date:
    return datetime.now(IST).date()


# ---------------------------------------------------------------- reading


async def get_case(session: AsyncSession, user: User, case_id: str) -> Case:
    query = (
        select(Case)
        .where(Case.id == case_id, Case.user_id == user.id)
        .options(selectinload(Case.questions), selectinload(Case.deadlines))
        .options(selectinload(Case.applicant))
        .execution_options(populate_existing=True)
    )
    case = (await session.execute(query)).scalar_one_or_none()
    if case is None:
        raise NotFound
    return case


async def list_cases(session: AsyncSession, user: User) -> list[Case]:
    query = (
        select(Case)
        .where(Case.user_id == user.id)
        .options(selectinload(Case.deadlines))
        .order_by(Case.created_at.desc())
    )
    return list((await session.execute(query)).scalars())


# ---------------------------------------------------------------- drafting


async def create_case(
    session: AsyncSession, user: User, *, language: str, jurisdiction: Jurisdiction
) -> Case:
    case = Case(user_id=user.id, language=language, jurisdiction=jurisdiction)
    session.add(case)
    await session.commit()
    return await get_case(session, user, case.id)


async def set_authority(session: AsyncSession, case: Case, data: AuthorityInput) -> None:
    for field, value in data.model_dump().items():
        setattr(case, field, value)
    await session.commit()


async def set_applicant(session: AsyncSession, case: Case, data: ApplicantInput) -> None:
    """Stored encrypted; one applicant per case, replaced in place on edit."""
    applicant = case.applicant or Applicant(user_id=case.user_id, name=data.name)
    for field, value in data.model_dump().items():
        setattr(applicant, field, value)
    case.applicant = applicant
    await session.commit()


async def add_question(
    session: AsyncSession, case: Case, llm: StructuredLLM, text: str
) -> Question:
    """FR-2: the rewrite step runs before anything is stored, so a model failure stores nothing."""
    result = await rewrite(llm, text, language=case.language)  # type: ignore[arg-type]
    last = select(func.coalesce(func.max(Question.position), 0)).where(Question.case_id == case.id)
    position = (await session.execute(last)).scalar_one() + 1
    details = {
        "records_requested": result.records_requested,
        "reason": result.reason,
        "suggestion": result.suggestion,
    }
    question = Question(
        case_id=case.id,
        position=position,
        original_text=text,
        rewritten_text=result.rewritten or None,
        details=json.dumps(details, ensure_ascii=False),
        personal_information=result.personal_information,
    )
    session.add(question)
    await session.commit()
    return question


def _question(case: Case, question_id: str) -> Question:
    question = next((q for q in case.questions if q.id == question_id), None)
    if question is None:
        raise NotFound
    return question


async def update_question(
    session: AsyncSession,
    case: Case,
    question_id: str,
    *,
    rewritten_text: str | None = None,
    accepted: bool | None = None,
) -> Question:
    question = _question(case, question_id)
    if rewritten_text is not None:
        question.rewritten_text = rewritten_text
    if accepted is not None:
        question.accepted = accepted
    await session.commit()
    return question


async def delete_question(session: AsyncSession, case: Case, question_id: str) -> None:
    await session.delete(_question(case, question_id))
    await session.commit()


def check(case: Case) -> tuple[Flag, ...]:
    """FR-3 on this case's current draft."""
    draft = Draft(
        jurisdiction=case.jurisdiction,
        questions=tuple(q.rewritten_text or q.original_text for q in case.questions),
        personal_information=any(q.personal_information for q in case.questions),
        pio_address=case.pio_address or "",
        applicant_address=(case.applicant.address if case.applicant else None) or "",
    )
    return validate(draft)


# ---------------------------------------------------------------- lifecycle


async def _transition(session: AsyncSession, case: Case, allowed: set[str], **values: Any) -> None:
    """Conditional update: applies only if the case is still in an allowed status."""
    statement = (
        update(Case)
        .where(Case.id == case.id, Case.status.in_(allowed))
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if (await session.execute(statement)).rowcount != 1:  # type: ignore[attr-defined]
        await session.rollback()
        raise WrongStatus
    await session.flush()


def _deadline(case: Case, kind: str) -> Deadline | None:
    return next((d for d in case.deadlines if d.kind == kind), None)


def _put_deadline(
    session: AsyncSession,
    case: Case,
    kind: str,
    due_on: date,
    estimated: bool,
    due_at: datetime | None = None,
) -> None:
    row = _deadline(case, kind) or Deadline(case_id=case.id, kind=kind)
    row.due_on, row.estimated, row.due_at = due_on, estimated, due_at
    row.reminded_7d_at = row.reminded_1d_at = row.reminded_due_at = None  # a new date reminds anew
    session.add(row)


def _engine_deadlines(case: Case, received_on: date | None) -> Any:
    return compute_deadlines(
        filed_on=case.filed_on,  # type: ignore[arg-type]
        received_on=received_on,
        via_apio=case.via_apio,
        third_party=case.third_party,
        life_liberty=case.life_liberty,
        rules=load_rules(case.jurisdiction),
    )


async def file_case(session: AsyncSession, case: Case, data: FilingInput) -> None:
    """FR-6/FR-7: record the filing, compute every deadline from the engine, start the clock."""
    await _transition(
        session,
        case,
        {CaseStatus.DRAFT.value},
        status=CaseStatus.REPLY_DUE.value,
        filed_on=data.filed_on,
        filing_mode=data.filing_mode,
    )
    case.filed_on, case.filing_mode = data.filed_on, data.filing_mode
    computed = _engine_deadlines(case, data.received_on)
    case.received_on = computed.received_on
    case.received_estimated = computed.received_estimated
    for deadline in (computed.pio_reply, computed.first_appeal):
        _put_deadline(
            session, case, deadline.kind, deadline.due_on, deadline.estimated, deadline.due_at
        )
    await session.commit()


async def set_receipt(session: AsyncSession, case: Case, received_on: date) -> None:
    """The authority's actual receipt date replaces the estimate: the clocks restart from it."""
    if case.filed_on is not None and received_on < case.filed_on:
        raise InvalidDate
    await _transition(
        session,
        case,
        {CaseStatus.REPLY_DUE.value},
        received_on=received_on,
        received_estimated=False,
    )
    computed = _engine_deadlines(case, received_on)
    case.received_on, case.received_estimated = computed.received_on, computed.received_estimated
    for deadline in (computed.pio_reply, computed.first_appeal):
        _put_deadline(
            session, case, deadline.kind, deadline.due_on, deadline.estimated, deadline.due_at
        )
    await session.commit()


async def record_reply(session: AsyncSession, case: Case, received_on: date) -> None:
    """The PIO replied: the first-appeal window now runs from the reply (S. 19(1))."""
    allowed = {CaseStatus.REPLY_DUE.value, CaseStatus.DEEMED_REFUSED.value}
    await _transition(
        session, case, allowed, status=CaseStatus.REPLIED.value, reply_received_on=received_on
    )
    case.reply_received_on = received_on
    pio_reply = _engine_deadlines(case, case.received_on).pio_reply
    appeal = first_appeal_deadline(
        pio_reply,
        rules=load_rules(case.jurisdiction),
        reply_received_on=received_on,
    )
    _put_deadline(session, case, appeal.kind, appeal.due_on, appeal.estimated)
    await session.commit()


async def close_case(session: AsyncSession, case: Case) -> None:
    open_statuses = {s.value for s in CaseStatus} - {CaseStatus.CLOSED.value}
    await _transition(
        session, case, open_statuses, status=CaseStatus.CLOSED.value, closed_on=today_ist()
    )
    await session.commit()


async def delete_case(session: AsyncSession, case: Case, storage_dir: Path) -> None:
    """FR-8: rows by cascade, then the stored files."""
    keys = [d.storage_key for d in await _documents(session, case)]
    await session.delete(case)
    await session.commit()
    remove_files(storage_dir, keys)


Renderer = Callable[[ApplicationDocument], bytes]


async def build_application(
    session: AsyncSession,
    case: Case,
    llm: StructuredLLM,
    renderer: Renderer,
    storage_dir: Path,
    *,
    payment_mode: str,
    place: str,
) -> bytes:
    """FR-5: compose, render and store the application. The model sees only the records;
    the applicant's name and address join the document after the model call (golden rule)."""
    blocking = [flag for flag in check(case) if flag.severity == "block"]
    records = [
        q.rewritten_text or q.original_text for q in case.questions if not q.personal_information
    ]
    if not records and not blocking:  # every question was refused as personal information
        blocking = [Flag(code="no_questions", severity="block")]
    if blocking or case.applicant is None:
        raise Blocked(blocking)
    applicant = case.applicant
    rules = load_rules(case.jurisdiction)
    if not applicant.bpl and payment_mode not in rules.local.payment_modes.modes:
        raise InvalidPaymentMode
    composed = await compose(
        llm,
        "Accepted records:\n" + "\n".join(f"- {r}" for r in records),
        language=case.language,  # type: ignore[arg-type]
    )
    document = ApplicationDocument(
        language=case.language,
        jurisdiction=case.jurisdiction,
        authority_name=case.authority_name or "",
        pio_address=case.pio_address or "",
        applicant_name=applicant.name,
        applicant_address=applicant.address or "",
        subject=composed.subject,
        questions=composed.questions,
        bpl=applicant.bpl,
        payment_mode=None if applicant.bpl else payment_mode,
        prepared_on=today_ist(),
        place=place,
    )
    pdf = await run_in_threadpool(renderer, document)  # WeasyPrint is CPU-bound
    await _replace_document(session, case, storage_dir, pdf, DocumentKind.APPLICATION)
    return pdf


async def _replace_document(
    session: AsyncSession, case: Case, storage_dir: Path, pdf: bytes, kind: DocumentKind
) -> None:
    """Keep one document of each kind per case: older copies are personal data we no longer
    need."""
    old = [d for d in await _documents(session, case) if d.kind == kind.value]
    key = save(storage_dir, pdf)
    for document in old:
        await session.delete(document)
    session.add(Document(case_id=case.id, kind=kind.value, storage_key=key))
    await session.commit()
    remove_files(storage_dir, [d.storage_key for d in old])


async def _documents(session: AsyncSession, case: Case) -> list[Document]:
    found = await session.execute(select(Document).where(Document.case_id == case.id))
    return list(found.scalars())


# ---------------------------------------------------------------- views


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def question_view(question: Question) -> dict[str, Any]:
    details = json.loads(question.details) if question.details else {}
    return {
        "id": question.id,
        "position": question.position,
        "original_text": question.original_text,
        "rewritten_text": question.rewritten_text,
        "records_requested": details.get("records_requested", []),
        "reason": details.get("reason"),
        "personal_information": question.personal_information,
        "suggestion": details.get("suggestion"),
        "accepted": question.accepted,
    }


def deadline_view(deadline: Deadline) -> dict[str, Any]:
    return {
        "kind": deadline.kind,
        "due_on": deadline.due_on.isoformat(),
        "due_at": deadline.due_at.isoformat() if deadline.due_at else None,
        "estimated": deadline.estimated,
    }


def case_view(case: Case) -> dict[str, Any]:
    """The Case object of docs/api.md. Applicant details are never echoed back."""
    return {
        "id": case.id,
        "language": case.language,
        "jurisdiction": case.jurisdiction,
        "status": case.status,
        "authority_name": case.authority_name,
        "pio_address": case.pio_address,
        "has_applicant": case.applicant is not None,
        "via_apio": case.via_apio,
        "third_party": case.third_party,
        "life_liberty": case.life_liberty,
        "filing_mode": case.filing_mode,
        "filed_on": case.filed_on.isoformat() if case.filed_on else None,
        "received_on": case.received_on.isoformat() if case.received_on else None,
        "received_estimated": case.received_estimated,
        "reply_received_on": _iso(case.reply_received_on),
        "appeal_filed_on": _iso(case.appeal_filed_on),
        "questions": [question_view(q) for q in case.questions],
        "deadlines": [deadline_view(d) for d in sorted(case.deadlines, key=lambda d: d.due_on)],
        "created_at": case.created_at.isoformat(),
    }


def case_summary(case: Case) -> dict[str, Any]:
    upcoming = sorted(case.deadlines, key=lambda d: d.due_on)
    nxt = upcoming[0] if upcoming and case.status != CaseStatus.CLOSED.value else None
    return {
        "id": case.id,
        "status": case.status,
        "authority_name": case.authority_name,
        "next_deadline": (
            {
                "kind": nxt.kind,
                "due_on": nxt.due_on.isoformat(),
                "due_at": nxt.due_at.isoformat() if nxt.due_at else None,
                "estimated": nxt.estimated,
            }
            if nxt
            else None
        ),
        "created_at": case.created_at.isoformat(),
    }


async def export_cases(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    """FR-8: the user's cases with their own details decrypted, for the export download."""
    exported = []
    for summary in await list_cases(session, user):
        case = await get_case(session, user, summary.id)
        applicant = case.applicant
        exported.append(
            {
                **case_view(case),
                "applicant": (
                    {
                        "name": applicant.name,
                        "address": applicant.address,
                        "phone": applicant.phone,
                        "bpl": applicant.bpl,
                    }
                    if applicant
                    else None
                ),
            }
        )
    return exported
