"""API shell: health, session cookie, account routes, Origin checks, CORS, errors, rate limits."""

import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy import func, select

from unseal.api.app import SESSION_COOKIE, create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, User
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import ModelBusy, ModelIncomplete, ModelOutputInvalid
from unseal.privacy.redact import RedactingFilter

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


def settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'api.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
        **overrides,
    )


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    yield await built(settings(tmp_path))


async def built(config: Settings) -> FastAPI:
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_app(config, session_factory=build_session_factory(engine))


def client(app: FastAPI, origin: str | None = WEB) -> httpx.AsyncClient:
    headers = {"Origin": origin} if origin else {}
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://api.test", headers=headers)


async def users(app: FastAPI) -> int:
    async with app.state.session_factory() as session:
        return (await session.execute(select(func.count()).select_from(User))).scalar_one()


async def test_health_needs_no_session(app: FastAPI) -> None:
    async with client(app, origin=None) as api:
        response = await api.get("/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_session_sets_a_secure_http_only_cookie_once(app: FastAPI) -> None:
    async with client(app) as api:
        first = await api.post("/session", json={"language": "ta"})
        again = await api.post("/session", json={"language": "en"})
    assert first.status_code == again.status_code == 204
    cookie = first.headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert all(part in cookie for part in ("httponly", "secure", "samesite=lax", "path=/"))
    assert "set-cookie" not in again.headers  # the valid cookie was reused
    assert await users(app) == 1


async def test_me_needs_a_session_and_reports_the_account(app: FastAPI) -> None:
    async with client(app) as api:
        assert (await api.get("/me")).json() == {"error": "no_session"}
        await api.post("/session", json={"language": "ta"})
        assert (await api.get("/me")).json() == {"language": "ta", "cases": 0}
        assert (await api.patch("/me", json={"language": "hi"})).status_code == 204
        assert (await api.get("/me")).json()["language"] == "hi"
        bad = await api.patch("/me", json={"language": "fr"})
    assert (bad.status_code, bad.json()["error"]) == (400, "invalid")


async def test_writes_need_the_app_origin(app: FastAPI) -> None:
    for origin in (None, "https://evil.example"):
        async with client(app, origin=origin) as api:
            response = await api.post("/session", json={"language": "en"})
        assert (response.status_code, response.json()) == (403, {"error": "bad_origin"})
    assert await users(app) == 0


async def test_cors_allows_only_the_app_origin(app: FastAPI) -> None:
    preflight = {"Access-Control-Request-Method": "POST"}
    async with client(app, origin=WEB) as api:
        ok = await api.options("/session", headers=preflight)
    async with client(app, origin="https://evil.example") as api:
        evil = await api.options("/session", headers=preflight)
    assert ok.headers["access-control-allow-origin"] == WEB
    assert ok.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in evil.headers


async def test_delete_me_removes_the_user_and_clears_the_cookie(app: FastAPI) -> None:
    async with client(app) as api:
        await api.post("/session", json={"language": "en"})
        response = await api.delete("/me")
        after = await api.get("/me")
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert after.json() == {"error": "no_session"}
    assert await users(app) == 0


async def test_export_is_an_attachment(app: FastAPI) -> None:
    async with client(app) as api:
        await api.post("/session", json={"language": "en"})
        response = await api.get("/me/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.json() == {"language": "en", "cases": []}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ModelBusy("busy"), 503, "busy"),
        (ModelOutputInvalid("bad"), 422, "ask_user"),
        (ModelIncomplete("max_output_tokens", "{"), 422, "incomplete"),
    ],
)
async def test_model_errors_become_contract_errors(
    app: FastAPI, error: Exception, status: int, code: str
) -> None:
    async def boom() -> None:
        raise error

    app.add_api_route("/boom", boom)
    async with client(app) as api:
        response = await api.get("/boom")
    assert (response.status_code, response.json()["error"]) == (status, code)


async def test_rate_limit_answers_429(tmp_path: Path) -> None:
    app = await built(settings(tmp_path, rate_limit_default="2/minute"))
    async with client(app) as api:
        codes = [(await api.get("/health")).status_code for _ in range(3)]
        limited = await api.get("/health")
    assert codes[:2] == [200, 200]
    assert (limited.status_code, limited.json()) == (429, {"error": "rate_limited"})


async def test_unknown_routes_answer_not_found(app: FastAPI) -> None:
    async with client(app) as api:
        response = await api.get("/nope")
    assert (response.status_code, response.json()) == (404, {"error": "not_found"})


async def test_startup_installs_log_redaction_on_uvicorn_loggers(app: FastAPI) -> None:
    handler = logging.StreamHandler()
    uvicorn_log = logging.getLogger("uvicorn.error")
    uvicorn_log.addHandler(handler)
    try:
        async with app.router.lifespan_context(app):
            assert any(isinstance(f, RedactingFilter) for f in handler.filters)
    finally:
        uvicorn_log.removeHandler(handler)
