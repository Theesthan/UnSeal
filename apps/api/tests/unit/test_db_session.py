"""Engine and session factory: SQLite foreign keys, error hygiene, and the FastAPI dependency."""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from unseal.db import session as session_module
from unseal.db.crypto import set_key_provider
from unseal.db.models import Applicant, Base, Case, User
from unseal.db.session import (
    _enable_sqlite_foreign_keys,
    build_engine,
    build_session_factory,
    dispose_engine,
    get_engine,
    get_session,
    get_session_factory,
)

pytestmark = pytest.mark.anyio

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    set_key_provider(lambda: TEST_KEY)
    yield
    set_key_provider(None)


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_sqlite_foreign_keys_are_switched_on(tmp_path: Path) -> None:
    engine = build_engine(sqlite_url(tmp_path / "fk.db"))
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
        # Every new pooled connection gets it, not just the first.
        async with engine.connect() as first, engine.connect() as second:
            for conn in (first, second):
                assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
    finally:
        await engine.dispose()


def test_the_pragma_is_only_registered_for_sqlite() -> None:
    # No sync_engine attribute: touching it would raise, so a non-SQLite engine is left alone.
    other = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    _enable_sqlite_foreign_keys(cast(AsyncEngine, other))


async def test_sessions_do_not_expire_objects_on_commit(tmp_path: Path) -> None:
    engine = build_engine(sqlite_url(tmp_path / "expire.db"))
    try:
        await create_tables(engine)
        async with build_session_factory(engine)() as session:
            user = User(channel="web", language="en")
            session.add(user)
            await session.commit()
            # Would raise MissingGreenlet if the commit had expired the object.
            assert user.language == "en"
    finally:
        await engine.dispose()


async def test_database_errors_do_not_echo_parameter_values(tmp_path: Path) -> None:
    # SQLAlchemy puts "[parameters: ...]" in exception text, which lands in logs and traces.
    marker = "Test Marker Authority 7f3a"
    engine = build_engine(sqlite_url(tmp_path / "hide.db"))
    try:
        await create_tables(engine)
        async with build_session_factory(engine)() as session:
            user = User(channel="web", language="en")
            applicant = Applicant(user=user, name="Test Applicant")
            session.add(applicant)
            await session.flush()
            session.add(
                Case(
                    user_id="missing-user",
                    applicant_id=applicant.id,
                    language="en",
                    jurisdiction="central",
                    authority_name=marker,
                )
            )
            with pytest.raises(IntegrityError) as caught:
                await session.flush()
        assert marker not in str(caught.value)
        assert "Test Applicant" not in str(caught.value)
    finally:
        await engine.dispose()


@pytest.fixture
def settings_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = sqlite_url(tmp_path / "app.db")
    monkeypatch.setattr(session_module, "_load_database_url", lambda: url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield url
    get_engine.cache_clear()
    get_session_factory.cache_clear()


async def test_the_default_engine_comes_from_settings_and_is_reused(
    settings_url: str,
) -> None:
    first = get_engine()
    assert first is get_engine()
    assert str(first.url).endswith("app.db")
    assert get_session_factory() is get_session_factory()
    await dispose_engine()


def test_the_database_url_is_read_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./somewhere.db")
    assert session_module._load_database_url() == "sqlite+aiosqlite:///./somewhere.db"


async def test_get_session_yields_a_working_session_and_discards_uncommitted_work(
    settings_url: str,
) -> None:
    await create_tables(get_engine())

    generator = get_session()
    session = await anext(generator)
    assert isinstance(session, AsyncSession)
    session.add(User(channel="web", language="en"))
    await session.flush()
    await generator.aclose()  # the request ended without a commit

    generator = get_session()
    session = await anext(generator)
    assert (await session.execute(text("SELECT count(*) FROM users"))).scalar_one() == 0
    session.add(User(channel="web", language="en"))
    await session.commit()
    await generator.aclose()

    async for session in get_session():
        assert (await session.execute(text("SELECT count(*) FROM users"))).scalar_one() == 1
    await dispose_engine()


async def test_dispose_engine_allows_a_fresh_engine(settings_url: str) -> None:
    before = get_engine()
    await dispose_engine()
    assert get_engine() is not before
    await dispose_engine()


async def test_dispose_engine_without_an_engine_is_a_no_op(settings_url: str) -> None:
    await dispose_engine()
