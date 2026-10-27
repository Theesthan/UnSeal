"""Settings from environment variables (and the repo-root .env in local dev). Secrets are SecretStr
so they never show up in a repr, log line or traceback."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/src/unseal/config.py -> repo root. Absent in a container, where env vars are used.
_REPO_ENV = Path(__file__).resolve().parents[4] / ".env"


def normalize_database_url(url: str) -> str:
    """Make a SQLite URL async. `.env.example` ships the plain `sqlite:///./dev.db` form, but the
    engine is async, so it needs the aiosqlite driver. Every other URL passes through unchanged."""
    if url.startswith("sqlite:"):
        return "sqlite+aiosqlite:" + url.removeprefix("sqlite:")
    return url


class DatabaseSettings(BaseSettings):
    """The settings the database layer and Alembic need. Kept apart from `Settings` so migrations
    run without BHARATCODE_API_KEY; `Settings` inherits both fields."""

    model_config = SettingsConfigDict(env_file=_REPO_ENV, extra="ignore")

    # A secret because a production URL carries the database password.
    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./dev.db")
    # One Fernet key, or several comma-separated for rotation (first encrypts, all decrypt).
    field_encryption_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _async_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if not raw:
            raise ValueError("DATABASE_URL must not be empty")
        return SecretStr(normalize_database_url(raw))

    @field_validator("field_encryption_key")
    @classmethod
    def _blank_key_is_missing(cls, value: SecretStr | None) -> SecretStr | None:
        # .env.example ships `FIELD_ENCRYPTION_KEY=` (empty): treat that as "not set".
        if value is None or not value.get_secret_value().strip():
            return None
        return value


class Settings(DatabaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ENV, extra="ignore")

    bharatcode_api_key: SecretStr
    bharatcode_base_url: str = "https://bharatcode.ai/api/model/v1"
    bharatcode_model: str = "qwen-3.8-27b"
    # Per request. Short in the app so users see "busy, try again"; the live eval raises it,
    # because BharatCode's shared GPU queue can take minutes per call.
    bharatcode_timeout_seconds: float = 120
