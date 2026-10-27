"""Database settings: URL normalisation, secret handling, and independence from the LLM key."""

import pytest
from pydantic import ValidationError

from unseal.config import DatabaseSettings, Settings, normalize_database_url

# Obviously fake values; nothing here is a real credential.
FAKE_PASSWORD = "test-db-password"
FAKE_FERNET_KEY = "test-key-value-not-a-real-key"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("sqlite:///./dev.db", "sqlite+aiosqlite:///./dev.db"),
        ("sqlite:///:memory:", "sqlite+aiosqlite:///:memory:"),
        ("sqlite://", "sqlite+aiosqlite://"),
        ("sqlite:///C:/tmp/unseal.db", "sqlite+aiosqlite:///C:/tmp/unseal.db"),
        ("sqlite+aiosqlite:///./dev.db", "sqlite+aiosqlite:///./dev.db"),
        (
            "postgresql+asyncpg://user:pw@db.example.test/unseal",
            "postgresql+asyncpg://user:pw@db.example.test/unseal",
        ),
    ],
)
def test_normalize_database_url(given: str, expected: str) -> None:
    assert normalize_database_url(given) == expected


def test_normalize_is_idempotent() -> None:
    once = normalize_database_url("sqlite:///./dev.db")
    assert normalize_database_url(once) == once


def test_defaults_are_a_local_async_sqlite_file_and_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    settings = DatabaseSettings(_env_file=None)
    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///./dev.db"
    assert settings.field_encryption_key is None


def test_plain_sqlite_url_from_the_environment_is_converted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This is the form .env.example ships.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./dev.db")
    settings = DatabaseSettings(_env_file=None)
    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///./dev.db"


def test_plain_sqlite_url_passed_directly_is_converted() -> None:
    settings = DatabaseSettings(_env_file=None, database_url="sqlite:///other.db")
    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///other.db"


def test_blank_database_url_is_rejected_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        DatabaseSettings(_env_file=None)


def test_database_url_is_a_secret_because_it_may_carry_a_password() -> None:
    url = f"postgresql+asyncpg://user:{FAKE_PASSWORD}@db.example.test/unseal"
    settings = DatabaseSettings(_env_file=None, database_url=url)
    assert FAKE_PASSWORD not in repr(settings)
    assert FAKE_PASSWORD not in str(settings)
    assert settings.database_url.get_secret_value() == url


def test_encryption_key_is_a_secret() -> None:
    settings = DatabaseSettings(_env_file=None, field_encryption_key=FAKE_FERNET_KEY)
    assert FAKE_FERNET_KEY not in repr(settings)
    assert settings.field_encryption_key is not None
    assert settings.field_encryption_key.get_secret_value() == FAKE_FERNET_KEY


def test_blank_encryption_key_means_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example ships FIELD_ENCRYPTION_KEY= (empty). That must read as "not set".
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "")
    assert DatabaseSettings(_env_file=None).field_encryption_key is None
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "  ")
    assert DatabaseSettings(_env_file=None).field_encryption_key is None


def test_database_settings_do_not_need_the_llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Alembic and the db package must run without BHARATCODE_API_KEY.
    monkeypatch.delenv("BHARATCODE_API_KEY", raising=False)
    DatabaseSettings(_env_file=None)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_still_carries_the_database_fields() -> None:
    settings = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url="sqlite:///x.db",
        field_encryption_key=FAKE_FERNET_KEY,
    )
    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///x.db"
    assert settings.bharatcode_timeout_seconds == 120
