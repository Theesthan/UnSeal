"""Scheduled jobs (APScheduler runs them every 15 minutes from the app lifespan).

Each job is a plain async function over a session and an explicit clock, so tests pin the time.
Dates come from deadline rows the rules engine computed; nothing here adds days except the
retention period, which is app policy (PRD privacy), not law.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from unseal.db.models import Case, CaseStatus, Deadline, DeadlineKind, Document
from unseal.rules.deadlines import IST
from unseal.services.storage import remove_files

logger = logging.getLogger(__name__)

RETENTION_DAYS = 180  # PRD: closed cases are deleted automatically after 180 days

# FR-9: remind 7 days before, 1 day before, and on the due date.
REMINDER_WINDOWS: dict[str, int] = {"7d": 7, "1d": 1, "due": 0}
_MARKERS: dict[str, InstrumentedAttribute[datetime | None]] = {
    "7d": Deadline.reminded_7d_at,
    "1d": Deadline.reminded_1d_at,
    "due": Deadline.reminded_due_at,
}
# A deadline only matters while the case is waiting on it.
_LIVE_STATUSES: dict[str, tuple[str, ...]] = {
    DeadlineKind.PIO_REPLY.value: (CaseStatus.REPLY_DUE.value,),
    DeadlineKind.FIRST_APPEAL.value: (
        CaseStatus.REPLY_DUE.value,
        CaseStatus.REPLIED.value,
        CaseStatus.DEEMED_REFUSED.value,
    ),
    DeadlineKind.FAA_DECISION.value: (CaseStatus.APPEALED.value,),
    DeadlineKind.SECOND_APPEAL.value: (CaseStatus.APPEALED.value,),
}


@dataclass(frozen=True)
class Reminder:
    deadline_id: str
    case_id: str
    kind: str
    due_on: date
    window: str


async def mark_deemed_refusals(session: AsyncSession, *, today: date) -> int:
    """S. 7(2): no reply by the PIO's deadline is a deemed refusal. The due date itself is in
    time. ponytail: day granularity; the 48-hour track flips on the next day's run."""
    overdue = select(Deadline.case_id).where(
        Deadline.kind == DeadlineKind.PIO_REPLY.value, Deadline.due_on < today
    )
    statement = (
        update(Case)
        .where(Case.status == CaseStatus.REPLY_DUE.value, Case.id.in_(overdue))
        .values(status=CaseStatus.DEEMED_REFUSED.value)
    )
    changed: int = (await session.execute(statement)).rowcount  # type: ignore[attr-defined]
    await session.commit()
    return changed


async def purge_closed_cases(session: AsyncSession, *, storage_dir: Path, today: date) -> int:
    """Delete closed cases older than the retention period, rows and stored files."""
    cutoff = today - timedelta(days=RETENTION_DAYS)
    expired = select(Case).where(Case.status == CaseStatus.CLOSED.value, Case.closed_on < cutoff)
    cases = list((await session.execute(expired)).scalars())
    ids = [case.id for case in cases]
    keys = await session.execute(select(Document.storage_key).where(Document.case_id.in_(ids)))
    storage_keys = list(keys.scalars())
    for case in cases:
        await session.delete(case)
    await session.commit()
    remove_files(storage_dir, storage_keys)
    return len(cases)


async def claim_reminders(session: AsyncSession, *, now: datetime) -> list[Reminder]:
    """Claim every reminder due now. Claim before send: the marker is set by a conditional
    update, so two schedulers, or two ticks, can never both send the same reminder."""
    today = now.astimezone(IST).date()
    claimed: list[Reminder] = []
    for window, days_before in REMINDER_WINDOWS.items():
        marker = _MARKERS[window]
        for row in await _candidates(session, marker, today + timedelta(days=days_before)):
            claim = (
                update(Deadline)
                .where(Deadline.id == row.id, marker.is_(None))
                .values({marker.key: now})
            )
            if (await session.execute(claim)).rowcount == 1:  # type: ignore[attr-defined]
                claimed.append(Reminder(row.id, row.case_id, row.kind, row.due_on, window))
    await session.commit()
    return claimed


async def _candidates(
    session: AsyncSession, marker: InstrumentedAttribute[datetime | None], due_on: date
) -> list[Deadline]:
    """Unreminded deadlines due on `due_on` whose case is still waiting on them (one query)."""
    live = or_(
        *(
            and_(Deadline.kind == kind, Case.status.in_(statuses))
            for kind, statuses in _LIVE_STATUSES.items()
        )
    )
    query = (
        select(Deadline)
        .join(Case, Case.id == Deadline.case_id)
        .where(Deadline.due_on == due_on, marker.is_(None), live)
    )
    return list((await session.execute(query)).scalars())


Send = Callable[[Reminder], Awaitable[None]]


async def _guarded(
    factory: async_sessionmaker[AsyncSession],
    name: str,
    job: Callable[[AsyncSession], Awaitable[object]],
) -> None:
    try:
        async with factory() as session:
            await job(session)
    except Exception:
        logger.exception("scheduler job %s failed", name)


async def tick(
    factory: async_sessionmaker[AsyncSession],
    *,
    storage_dir: Path,
    now: datetime,
    send: Send | None,
) -> None:
    """One scheduler run: every job, each in its own session so one failure stops no other.
    Without a sender nothing is claimed, so no reminder is lost while the bot is off."""
    today = now.astimezone(IST).date()
    await _guarded(factory, "deemed_refusals", lambda s: mark_deemed_refusals(s, today=today))
    await _guarded(
        factory,
        "retention",
        lambda s: purge_closed_cases(s, storage_dir=storage_dir, today=today),
    )
    if send is None:
        return
    async with factory() as session:
        reminders = await claim_reminders(session, now=now)
    for reminder in reminders:
        try:
            await send(reminder)
        except Exception:  # ponytail: claimed, so a failed send is lost (at most once); retry
            # queue if delivery failures show up in the logs
            logger.exception(
                "reminder %s for deadline %s not sent", reminder.window, reminder.deadline_id
            )
