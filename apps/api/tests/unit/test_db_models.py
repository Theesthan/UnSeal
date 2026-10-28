"""Models: deletion cascades, uniqueness, constrained values, defaults and types."""

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from unseal.db.crypto import set_key_provider
from unseal.db.models import (
    Applicant,
    Base,
    Case,
    CaseStatus,
    Channel,
    Deadline,
    DeadlineKind,
    Document,
    DocumentKind,
    Language,
    Question,
    User,
    UTCDateTime,
)
from unseal.db.session import build_engine, build_session_factory

pytestmark = pytest.mark.anyio

TEST_KEY = Fernet.generate_key().decode()
TABLES = ("users", "applicants", "cases", "questions", "deadlines", "documents")

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    set_key_provider(lambda: TEST_KEY)
    yield
    set_key_provider(None)


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    eng = build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'models.db').as_posix()}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def factory(engine: AsyncEngine) -> Factory:
    return build_session_factory(engine)


def new_graph(tag: str = "a") -> tuple[User, Applicant, Case]:
    """One user, one applicant and one draft case, none of them saved yet."""
    user = User(channel="web", language="en")
    applicant = Applicant(
        user=user, name=f"Test Applicant {tag}", address="Flat 0, Sample Nagar, Testville"
    )
    case = Case(user=user, applicant=applicant, language="en", jurisdiction="central")
    return user, applicant, case


async def seed_user(factory: Factory, tag: str, n_cases: int = 2) -> str:
    """A user with an applicant and `n_cases` cases, each with 2 questions, 2 deadlines, 1 file."""
    async with factory() as session:
        user = User(channel="web", language="en")
        applicant = Applicant(
            user=user, name=f"Test Applicant {tag}", address="Flat 0, Sample Nagar, Testville"
        )
        for i in range(n_cases):
            case = Case(
                user=user,
                applicant=applicant,
                language="en",
                jurisdiction="central",
                authority_name=f"Test Department {tag}",
            )
            case.questions.extend(
                [
                    Question(position=1, original_text=f"Test question {tag} {i} a"),
                    Question(position=2, original_text=f"Test question {tag} {i} b"),
                ]
            )
            case.deadlines.extend(
                [
                    Deadline(kind="pio_reply", due_on=date(2026, 12, 1)),
                    Deadline(kind="first_appeal", due_on=date(2027, 1, 1)),
                ]
            )
            case.documents.append(Document(kind="application", storage_key=f"{tag}-{i}-app"))
        session.add(user)
        await session.commit()
        return user.id


async def counts(factory: Factory) -> dict[str, int]:
    async with factory() as session:
        return {
            table: (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            for table in TABLES
        }


async def case_ids(factory: Factory, user_id: str) -> list[str]:
    async with factory() as session:
        rows = await session.scalars(select(Case.id).where(Case.user_id == user_id))
        return sorted(rows.all())


# --- deletion -----------------------------------------------------------------------------


@pytest.mark.parametrize("preload", [False, True], ids=["unloaded", "preloaded"])
async def test_deleting_a_user_removes_every_related_row(factory: Factory, preload: bool) -> None:
    keep = await seed_user(factory, "keep")
    gone = await seed_user(factory, "gone")
    assert await counts(factory) == {
        "users": 2,
        "applicants": 2,
        "cases": 4,
        "questions": 8,
        "deadlines": 8,
        "documents": 4,
    }
    async with factory() as session:
        stmt = select(User).where(User.id == gone)
        if preload:
            stmt = stmt.options(
                selectinload(User.applicants),
                selectinload(User.cases).options(
                    selectinload(Case.questions),
                    selectinload(Case.deadlines),
                    selectinload(Case.documents),
                ),
            )
        user = (await session.execute(stmt)).scalar_one()
        await session.delete(user)
        await session.commit()

    assert await counts(factory) == {
        "users": 1,
        "applicants": 1,
        "cases": 2,
        "questions": 4,
        "deadlines": 4,
        "documents": 2,
    }
    async with factory() as session:
        assert (await session.scalars(select(User.id))).all() == [keep]
        names = (await session.scalars(select(Applicant.user_id))).all()
        assert names == [keep]


async def test_a_bulk_delete_of_a_user_cascades_in_the_database(factory: Factory) -> None:
    # No ORM involved: this proves the ON DELETE CASCADE foreign keys (and the SQLite pragma).
    keep = await seed_user(factory, "keep")
    gone = await seed_user(factory, "gone")
    async with factory() as session:
        await session.execute(delete(User).where(User.id == gone))
        await session.commit()
    assert await counts(factory) == {
        "users": 1,
        "applicants": 1,
        "cases": 2,
        "questions": 4,
        "deadlines": 4,
        "documents": 2,
    }
    async with factory() as session:
        assert (await session.scalars(select(User.id))).all() == [keep]


@pytest.mark.parametrize("bulk", [False, True], ids=["orm", "bulk"])
async def test_deleting_a_case_removes_its_children_only(factory: Factory, bulk: bool) -> None:
    user_id = await seed_user(factory, "a")
    other_id = await seed_user(factory, "b")
    first, second = await case_ids(factory, user_id)
    async with factory() as session:
        if bulk:
            await session.execute(delete(Case).where(Case.id == first))
        else:
            case = await session.get(Case, first)
            assert case is not None
            await session.delete(case)
        await session.commit()

    assert await counts(factory) == {
        "users": 2,
        "applicants": 2,
        "cases": 3,
        "questions": 6,
        "deadlines": 6,
        "documents": 3,
    }
    async with factory() as session:
        for model in (Question, Deadline, Document):
            owners = set((await session.scalars(select(model.case_id))).all())
            assert first not in owners
            assert second in owners
        assert await session.get(Case, second) is not None
        assert await session.get(User, user_id) is not None
        applicants = (await session.scalars(select(Applicant.user_id))).all()
        assert sorted(applicants) == sorted([user_id, other_id])


async def test_deleting_an_applicant_removes_their_cases(factory: Factory) -> None:
    user_id = await seed_user(factory, "a")
    await seed_user(factory, "b")
    async with factory() as session:
        applicant = (
            await session.scalars(select(Applicant).where(Applicant.user_id == user_id))
        ).one()
        await session.delete(applicant)
        await session.commit()
    assert await case_ids(factory, user_id) == []
    counted = await counts(factory)
    assert counted["cases"] == 2
    assert counted["questions"] == 4


async def test_a_case_cannot_point_at_a_missing_user(factory: Factory) -> None:
    async with factory() as session:
        _, applicant, _ = new_graph()
        session.add(applicant)
        await session.flush()
        session.add(
            Case(
                user_id="no-such-user",
                applicant_id=applicant.id,
                language="en",
                jurisdiction="central",
            )
        )
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            await session.flush()


# --- uniqueness ---------------------------------------------------------------------------


async def test_a_case_has_at_most_one_deadline_of_each_kind(factory: Factory) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.deadlines.append(Deadline(kind="pio_reply", due_on=date(2026, 12, 1)))
        session.add(case)
        await session.commit()
        session.add(Deadline(case_id=case.id, kind="pio_reply", due_on=date(2026, 12, 9)))
        with pytest.raises(IntegrityError, match="UNIQUE"):
            await session.flush()


async def test_the_same_deadline_kind_is_allowed_on_different_cases(factory: Factory) -> None:
    async with factory() as session:
        user, applicant, case = new_graph()
        other = Case(user=user, applicant=applicant, language="en", jurisdiction="central")
        case.deadlines.append(Deadline(kind="pio_reply", due_on=date(2026, 12, 1)))
        other.deadlines.append(Deadline(kind="pio_reply", due_on=date(2026, 12, 2)))
        case.deadlines.append(Deadline(kind="first_appeal", due_on=date(2027, 1, 1)))
        session.add(user)
        await session.commit()
    assert (await counts(factory))["deadlines"] == 3


async def test_a_storage_key_belongs_to_one_document(factory: Factory) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.documents.append(Document(kind="application", storage_key="same-key"))
        session.add(case)
        await session.commit()
        session.add(Document(case_id=case.id, kind="first_appeal", storage_key="same-key"))
        with pytest.raises(IntegrityError, match="UNIQUE"):
            await session.flush()


# --- constrained values -------------------------------------------------------------------


def test_the_allowed_values_are_the_agreed_ones() -> None:
    assert {s.value for s in CaseStatus} == {
        "draft",
        "filed",
        "reply_due",
        "replied",
        "deemed_refused",
        "appealed",
        "closed",
    }
    assert {k.value for k in DeadlineKind} == {
        "pio_reply",
        "first_appeal",
        "faa_decision",
        "second_appeal",
    }
    assert {k.value for k in DocumentKind} == {
        "application",
        "first_appeal",
        "second_appeal",
        "reply_image",
    }
    assert {x.value for x in Language} == {"en", "hi", "ta"}
    assert {x.value for x in Channel} == {"web", "telegram"}


@pytest.mark.parametrize("status", list(CaseStatus))
async def test_every_case_status_is_accepted(factory: Factory, status: CaseStatus) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.status = status
        session.add(case)
        await session.commit()
    async with factory() as session:
        stored = (await session.execute(text("SELECT status FROM cases"))).scalar_one()
    assert stored == status.value


def _bad_status(case: Case, user: User, applicant: Applicant) -> object:
    case.status = "bogus"
    return case


def _bad_case_language(case: Case, user: User, applicant: Applicant) -> object:
    case.language = "fr"
    return case


def _bad_user_language(case: Case, user: User, applicant: Applicant) -> object:
    user.language = "fr"
    return user


def _bad_channel(case: Case, user: User, applicant: Applicant) -> object:
    user.channel = "whatsapp"
    return user


def _bad_deadline_kind(case: Case, user: User, applicant: Applicant) -> object:
    deadline = Deadline(kind="bogus", due_on=date(2026, 12, 1))
    case.deadlines.append(deadline)
    return deadline


def _bad_document_kind(case: Case, user: User, applicant: Applicant) -> object:
    document = Document(kind="bogus", storage_key="k")
    case.documents.append(document)
    return document


@pytest.mark.parametrize(
    ("mutate", "constraint"),
    [
        (_bad_status, "ck_cases_status"),
        (_bad_case_language, "ck_cases_language"),
        (_bad_user_language, "ck_users_language"),
        (_bad_channel, "ck_users_channel"),
        (_bad_deadline_kind, "ck_deadlines_kind"),
        (_bad_document_kind, "ck_documents_kind"),
    ],
    ids=["status", "case_language", "user_language", "channel", "deadline_kind", "document_kind"],
)
async def test_values_outside_the_allowed_set_are_rejected(
    factory: Factory, mutate: Callable[[Case, User, Applicant], object], constraint: str
) -> None:
    async with factory() as session:
        user, applicant, case = new_graph()
        mutate(case, user, applicant)
        session.add(user)
        with pytest.raises(IntegrityError, match=constraint):
            await session.commit()


# --- defaults, types ----------------------------------------------------------------------


async def test_new_rows_get_uuid4_ids_and_safe_defaults(factory: Factory) -> None:
    async with factory() as session:
        user, applicant, case = new_graph()
        question = Question(position=1, original_text="Test question")
        deadline = Deadline(kind="pio_reply", due_on=date(2026, 12, 1))
        document = Document(kind="application", storage_key="k1")
        case.questions.append(question)
        case.deadlines.append(deadline)
        case.documents.append(document)
        session.add(user)
        await session.commit()

        for row in (user, applicant, case, question, deadline, document):
            parsed = uuid.UUID(row.id)
            assert parsed.version == 4
            assert str(parsed) == row.id
        assert case.status == "draft"
        assert (case.via_apio, case.third_party, case.life_liberty) == (False, False, False)
        assert case.closed_on is None
        assert case.transferred_to is None
        assert case.transfer_received_on is None
        assert question.accepted is False
        assert question.flags == []
        assert deadline.estimated is False
        assert deadline.due_at is None
        assert (deadline.reminded_7d_at, deadline.reminded_1d_at, deadline.reminded_due_at) == (
            None,
            None,
            None,
        )
        assert datetime.now(UTC) - user.created_at < timedelta(minutes=1)
        assert user.created_at.tzinfo is not None


async def test_timestamps_round_trip_as_utc(factory: Factory) -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    due = datetime(2026, 11, 20, 18, 30, tzinfo=ist)
    async with factory() as session:
        _, _, case = new_graph()
        deadline = Deadline(kind="pio_reply", due_on=date(2026, 11, 20), due_at=due)
        deadline.reminded_7d_at = datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
        case.deadlines.append(deadline)
        session.add(case)
        await session.commit()
    async with factory() as session:
        loaded = (await session.scalars(select(Deadline))).one()
        assert loaded.due_at == due
        assert loaded.due_at is not None
        assert loaded.due_at.utcoffset() == timedelta(0)
        assert loaded.reminded_7d_at == datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
        raw = (await session.execute(text("SELECT due_at FROM deadlines"))).scalar_one()
    assert raw.startswith("2026-11-20 13:00:00")  # stored as UTC


async def test_a_naive_timestamp_is_refused(factory: Factory) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.deadlines.append(
            Deadline(kind="pio_reply", due_on=date(2026, 11, 20), due_at=datetime(2026, 11, 20, 1))
        )
        session.add(case)
        with pytest.raises(StatementError, match="timezone"):
            await session.commit()


async def test_dates_and_flags_round_trip(factory: Factory) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.filed_on = date(2026, 11, 1)
        case.received_on = date(2026, 11, 4)
        case.closed_on = date(2027, 2, 1)
        case.transferred_to = "Test Transfer Authority"
        case.transfer_received_on = date(2026, 11, 9)
        case.filing_mode = "post"
        case.pio_address = "Test PIO, 1 Sample Road, Testville"
        case.questions.append(
            Question(
                position=1,
                original_text="Why was my result lowered?",
                rewritten_text="Certified copy of the evaluated answer script.",
                accepted=True,
                flags=["why_question"],
            )
        )
        session.add(case)
        await session.commit()
    async with factory() as session:
        loaded = (await session.scalars(select(Case))).one()
        assert loaded.filed_on == date(2026, 11, 1)
        assert loaded.received_on == date(2026, 11, 4)
        assert loaded.closed_on == date(2027, 2, 1)
        assert loaded.transferred_to == "Test Transfer Authority"
        assert loaded.transfer_received_on == date(2026, 11, 9)
        question = (await session.scalars(select(Question))).one()
        assert question.accepted is True
        assert question.flags == ["why_question"]


async def test_questions_come_back_in_position_order(factory: Factory) -> None:
    async with factory() as session:
        _, _, case = new_graph()
        case.questions.extend(
            [
                Question(position=3, original_text="third"),
                Question(position=1, original_text="first"),
                Question(position=2, original_text="second"),
            ]
        )
        session.add(case)
        await session.commit()
        case_id = case.id
    async with factory() as session:
        loaded = (
            await session.scalars(
                select(Case).where(Case.id == case_id).options(selectinload(Case.questions))
            )
        ).one()
        assert [q.original_text for q in loaded.questions] == ["first", "second", "third"]


async def test_relationships_navigate_both_ways(factory: Factory) -> None:
    await seed_user(factory, "nav", n_cases=1)
    async with factory() as session:
        case = (
            await session.scalars(
                select(Case).options(
                    selectinload(Case.user),
                    selectinload(Case.applicant),
                    selectinload(Case.questions).selectinload(Question.case),
                    selectinload(Case.deadlines).selectinload(Deadline.case),
                    selectinload(Case.documents).selectinload(Document.case),
                )
            )
        ).one()
        assert case.applicant.name == "Test Applicant nav"
        assert case.user.id == case.user_id
        assert all(q.case is case for q in case.questions)
        assert all(d.case is case for d in case.deadlines)
        assert all(d.case is case for d in case.documents)
        applicant = (
            await session.scalars(
                select(Applicant).options(
                    selectinload(Applicant.cases), selectinload(Applicant.user)
                )
            )
        ).one()
        assert applicant.cases == [case]
        assert applicant.user.id == case.user_id


async def test_the_retention_query_selects_by_status_and_age(factory: Factory) -> None:
    # Documents the shape the retention job will use: closed AND closed_on before the cutoff.
    async with factory() as session:
        user, applicant, _ = new_graph()
        for status, closed_on in [
            ("closed", date(2026, 1, 1)),
            ("closed", date(2026, 9, 1)),
            ("replied", date(2026, 1, 1)),
        ]:
            session.add(
                Case(
                    user=user,
                    applicant=applicant,
                    language="en",
                    jurisdiction="central",
                    status=status,
                    closed_on=closed_on,
                )
            )
        await session.commit()
        cutoff = date(2026, 10, 27) - timedelta(days=180)
        due = await session.scalar(
            select(func.count())
            .select_from(Case)
            .where(Case.status == "closed", Case.closed_on < cutoff)
        )
    assert due == 1


def test_utc_datetime_converts_aware_values_read_back_from_other_databases() -> None:
    # SQLite drops the zone; Postgres keeps it, possibly in the session's zone.
    ist = timezone(timedelta(hours=5, minutes=30))
    column_type = UTCDateTime()
    aware = datetime(2026, 11, 20, 18, 30, tzinfo=ist)
    assert column_type.process_result_value(aware, None) == datetime(  # type: ignore[arg-type]
        2026, 11, 20, 13, 0, tzinfo=UTC
    )
    assert column_type.process_result_value(None, None) is None  # type: ignore[arg-type]
    naive = datetime(2026, 11, 20, 13, 0)
    assert column_type.process_result_value(naive, None).tzinfo is UTC  # type: ignore[arg-type,union-attr]
