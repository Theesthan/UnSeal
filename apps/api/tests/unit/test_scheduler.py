"""Scheduler jobs: deemed refusal (S. 7(2)), 180-day retention, reminder claims (FR-9)."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, Case, Deadline, Document, User
from unseal.db.session import build_engine, build_session_factory
from unseal.scheduler import (
    RETENTION_DAYS,
    claim_reminders,
    mark_deemed_refusals,
    purge_closed_cases,
)
from unseal.services.storage import path_for, save

pytestmark = pytest.mark.anyio

TODAY = date(2026, 12, 1)
NOW = datetime(2026, 12, 1, 4, 30, tzinfo=UTC)  # 10:00 IST


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'jobs.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield build_session_factory(engine)
    await engine.dispose()


async def add_case(
    session: AsyncSession, status: str, *, closed_on: date | None = None, due: date | None = None
) -> str:
    user = User(channel="web", language="en")
    case = Case(
        user=user, language="en", jurisdiction="central", status=status, closed_on=closed_on
    )
    session.add(case)
    if due is not None:
        session.add(Deadline(case=case, kind="pio_reply", due_on=due, estimated=False))
    await session.commit()
    return case.id


async def statuses(session: AsyncSession) -> dict[str, str]:
    return {c.id: c.status for c in (await session.execute(select(Case))).scalars()}


async def test_reply_due_past_its_deadline_becomes_deemed_refused(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        overdue = await add_case(session, "reply_due", due=TODAY - timedelta(days=1))
        due_today = await add_case(session, "reply_due", due=TODAY)
        replied = await add_case(session, "replied", due=TODAY - timedelta(days=5))
        assert await mark_deemed_refusals(session, today=TODAY) == 1
        assert await mark_deemed_refusals(session, today=TODAY) == 0  # idempotent
        found = await statuses(session)
    assert found[overdue] == "deemed_refused"
    assert found[due_today] == "reply_due"  # the due date itself is still in time
    assert found[replied] == "replied"


async def test_closed_cases_are_purged_after_the_retention_period(
    factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    storage = tmp_path / "storage"
    async with factory() as session:
        old = await add_case(
            session, "closed", closed_on=TODAY - timedelta(days=RETENTION_DAYS + 1)
        )
        edge = await add_case(session, "closed", closed_on=TODAY - timedelta(days=RETENTION_DAYS))
        open_case = await add_case(session, "reply_due", due=TODAY + timedelta(days=9))
        key = save(storage, b"%PDF-1.7 old")
        session.add(Document(case_id=old, kind="application", storage_key=key))
        await session.commit()
        assert await purge_closed_cases(session, storage_dir=storage, today=TODAY) == 1
        remaining = set(await statuses(session))
        documents = (await session.execute(select(func.count()).select_from(Document))).scalar()
    assert remaining == {edge, open_case}
    assert documents == 0 and not path_for(storage, key).exists()


async def test_each_reminder_window_is_claimed_exactly_once(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        await add_case(session, "reply_due", due=TODAY + timedelta(days=7))
        await add_case(session, "reply_due", due=TODAY + timedelta(days=1))
        await add_case(session, "reply_due", due=TODAY)
        await add_case(session, "reply_due", due=TODAY + timedelta(days=3))  # no window today
        await add_case(session, "closed", closed_on=TODAY, due=TODAY)  # closed: never reminded
        first = await claim_reminders(session, now=NOW)
        second = await claim_reminders(session, now=NOW + timedelta(minutes=15))
    assert sorted(r.window for r in first) == ["1d", "7d", "due"]
    assert second == []  # the next tick claims nothing again


async def test_two_schedulers_racing_claim_once(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        await add_case(session, "reply_due", due=TODAY)
    async with factory() as one, factory() as two:
        claims = await claim_reminders(one, now=NOW) + await claim_reminders(two, now=NOW)
    assert len(claims) == 1
