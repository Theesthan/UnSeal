"""POST /cases/{id}/reply/read (FR-11): consent first, bounded upload, nothing stored."""

import io
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import func, select

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, Document
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import ModelBusy, StructuredResult
from unseal.llm.schemas import ReplyRead

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"
READING = ReplyRead(
    letter_date="2026-09-01",
    items=[{"number": 1, "status": "refused", "section_cited": "8(1)(j)"}],  # type: ignore[list-item]
    fee_demanded=False,
    transferred_to=None,
)


class FakeLLM:
    def __init__(self, *results: ReplyRead | Exception) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return StructuredResult(item, "req-1", 0, False)


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("unseal.services.reply_reader.today_ist", lambda: date(2026, 10, 20))


async def make_app(tmp_path: Path, *results: ReplyRead | Exception) -> FastAPI:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'read.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
    )
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_app(config, session_factory=build_session_factory(engine), llm=FakeLLM(*results))


@asynccontextmanager
async def signed_in(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test", headers={"Origin": WEB}
    ) as api:
        await api.post("/session", json={"language": "hi"})
        yield api


async def case_id(api: httpx.AsyncClient, *, filed: bool = True) -> str:
    cid: str = (await api.post("/cases", json={"language": "hi"})).json()["id"]
    if filed:
        body = {"filed_on": "2026-08-03", "filing_mode": "post", "received_on": "2026-08-08"}
        await api.post(f"/cases/{cid}/filing", json=body)
    return cid


def photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(buffer, format="PNG")
    return buffer.getvalue()


async def upload(
    api: httpx.AsyncClient, cid: str, data: bytes, consent: str = "true"
) -> httpx.Response:
    return await api.post(
        f"/cases/{cid}/reply/read",
        files={"file": ("reply.png", data, "image/png")},
        data={"consent": consent},
    )


async def test_the_reply_is_read_and_nothing_is_stored(tmp_path: Path) -> None:
    app = await make_app(tmp_path, READING)
    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await upload(api, cid, photo())
        case = (await api.get(f"/cases/{cid}")).json()
    assert response.status_code == 200, response.text
    assert response.json() == {
        "letter_date": "2026-09-01",
        "items": [{"number": 1, "status": "refused", "section_cited": "8(1)(j)"}],
        "fee_demanded": False,
        "transferred_to": None,
        "suggested_grounds": ["refused"],
    }
    assert case["status"] == "reply_due" and case["reply_received_on"] is None
    assert "Hindi" in app.state.llm.calls[0]["instructions"]
    async with app.state.session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Document))).scalar() == 0
    assert not (tmp_path / "storage").exists() or not any((tmp_path / "storage").iterdir())


async def test_without_consent_the_photo_never_reaches_the_model(tmp_path: Path) -> None:
    app = await make_app(tmp_path, READING)
    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await upload(api, cid, photo(), consent="false")
    assert (response.status_code, response.json()) == (400, {"error": "consent_required"})
    assert app.state.llm.calls == []


async def test_an_oversized_upload_is_refused_before_it_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("unseal.services.reply_reader.MAX_UPLOAD_BYTES", 1000)
    app = await make_app(tmp_path, READING)
    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await upload(api, cid, photo() + b"\0" * 2000)
    assert (response.status_code, response.json()) == (413, {"error": "too_large"})
    assert app.state.llm.calls == []


async def test_a_file_that_is_not_a_letter_is_unreadable(tmp_path: Path) -> None:
    app = await make_app(tmp_path, READING)
    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await upload(api, cid, b"not an image at all")
    assert (response.status_code, response.json()) == (400, {"error": "unreadable_file"})


async def test_a_draft_has_no_reply_to_read(tmp_path: Path) -> None:
    app = await make_app(tmp_path, READING)
    async with signed_in(app) as api:
        cid = await case_id(api, filed=False)
        response = await upload(api, cid, photo())
    assert (response.status_code, response.json()) == (409, {"error": "wrong_status"})


async def test_a_busy_model_is_busy(tmp_path: Path) -> None:
    app = await make_app(tmp_path, ModelBusy("busy"))
    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await upload(api, cid, photo())
    assert (response.status_code, response.json()) == (503, {"error": "busy"})


async def test_a_chunked_upload_without_a_length_is_refused(tmp_path: Path) -> None:
    app = await make_app(tmp_path, READING)

    async def body() -> AsyncIterator[bytes]:
        yield b"--x\r\nContent-Disposition: form-data; name=consent\r\n\r\ntrue\r\n--x--\r\n"

    async with signed_in(app) as api:
        cid = await case_id(api)
        response = await api.post(
            f"/cases/{cid}/reply/read",
            content=body(),
            headers={"Content-Type": "multipart/form-data; boundary=x"},
        )
    assert (response.status_code, response.json()) == (411, {"error": "length_required"})
    assert app.state.llm.calls == []
