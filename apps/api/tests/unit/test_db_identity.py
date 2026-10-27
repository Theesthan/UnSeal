"""Migration 0002: identity hashes (ADR 0003) and encrypted question text."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Applicant, Base, Case, Question, User
from unseal.db.session import build_engine, build_session_factory

pytestmark = pytest.mark.anyio

API_DIR = Path(__file__).resolve().parents[2]
TEST_KEY = Fernet.generate_key().decode()
GRIEVANCE = "Why was register number TEST-0001 failed in mathematics?"


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    set_key_provider(lambda: TEST_KEY)
    yield
    set_key_provider(None)


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'id.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield build_session_factory(engine)
    await engine.dispose()


async def test_question_text_is_encrypted_at_rest(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        user = User(channel="web", language="en")
        applicant = Applicant(user=user, name="Test Applicant", address="1 Sample Road")
        case = Case(user=user, applicant=applicant, language="en", jurisdiction="central")
        session.add(
            Question(case=case, position=1, original_text=GRIEVANCE, rewritten_text=GRIEVANCE)
        )
        await session.commit()
        raw = (
            await session.execute(text("SELECT original_text, rewritten_text FROM questions"))
        ).one()
        assert all("TEST-0001" not in value for value in raw)
        stored = (await session.execute(select(Question))).scalar_one()
        assert stored.original_text == GRIEVANCE and stored.rewritten_text == GRIEVANCE


@pytest.mark.parametrize("column", ["session_token_hash", "telegram_chat_hash"])
async def test_identity_hashes_are_unique_and_optional(
    factory: async_sessionmaker[AsyncSession], column: str
) -> None:
    async with factory() as session:
        session.add_all([User(channel="web", language="en"), User(channel="web", language="ta")])
        await session.commit()  # two users without the hash: allowed
    async with factory() as session:
        session.add_all(
            [User(channel="web", language="en", **{column: "a" * 64}) for _ in range(2)]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


def test_migration_0004_is_the_head() -> None:
    script = ScriptDirectory.from_config(Config(str(API_DIR / "alembic.ini")))
    assert script.get_current_head() == "0004"


def test_api_settings_have_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_BASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_HASH_KEY", raising=False)
    settings = Settings(_env_file=None, bharatcode_api_key="k")
    assert settings.app_base_url == "http://localhost:3000"
    assert settings.telegram_bot_token is None
    assert settings.telegram_webhook_secret is None
    assert settings.telegram_chat_hash_key is None
    assert settings.storage_dir == Path("./storage")


def test_blank_telegram_secrets_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")  # .env.example ships these empty
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    settings = Settings(_env_file=None, bharatcode_api_key="k")
    assert settings.telegram_bot_token is None
    assert settings.telegram_webhook_secret is not None
    assert settings.telegram_webhook_secret.get_secret_value() == "test-webhook-secret"
