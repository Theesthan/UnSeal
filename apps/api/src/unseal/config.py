"""Settings from environment variables (and the repo-root .env in local dev). Secrets are SecretStr
so they never show up in a repr, log line or traceback."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/src/unseal/config.py -> repo root. Absent in a container, where env vars are used.
_REPO_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ENV, extra="ignore")

    bharatcode_api_key: SecretStr
    bharatcode_base_url: str = "https://bharatcode.ai/api/model/v1"
    bharatcode_model: str = "qwen-3.8-27b"
