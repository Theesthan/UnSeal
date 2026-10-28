"""ASGI entry point: `uv run uvicorn unseal.main:app`. Reads settings from the environment and
wires the real BharatCode client; tests build their own app with fakes via `create_app`."""

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.llm.client import build_client

settings = Settings()
app = create_app(settings, llm=build_client(settings))
