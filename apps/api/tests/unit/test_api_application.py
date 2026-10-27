"""FR-5 export: validation gate, compose, PDF render, storage; no personal data to the model."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, Document
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import StructuredResult
from unseal.llm.schemas import Compose, Rewrite
from unseal.pdf.models import ApplicationDocument
from unseal.services.storage import path_for

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"
NAME, ADDRESS = "Test Applicant", "12 Sample Street, Chennai"
REWRITE = Rewrite(
    rewritten="Certified copy of the work order for the ward road",
    records_requested=["work order"],
    reason="Records instead of reasons",
    personal_information=False,
    suggestion=None,
)
COMPOSE = Compose(
    subject="Work order for the ward road",
    questions=["Certified copy of the work order for the ward road"],
)


class FakeLLM:
    def __init__(self, *results: BaseModel) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        return StructuredResult(self.results.pop(0), "req-1", 0, False)


class FakeRenderer:
    def __init__(self) -> None:
        self.documents: list[ApplicationDocument] = []

    def __call__(self, doc: ApplicationDocument) -> bytes:
        self.documents.append(doc)
        return b"%PDF-1.7 fake " + str(len(self.documents)).encode()


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
    )
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    llm = FakeLLM(REWRITE, COMPOSE, COMPOSE)
    yield create_app(
        config, session_factory=build_session_factory(engine), llm=llm, renderer=FakeRenderer()
    )


@asynccontextmanager
async def signed_in(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test", headers={"Origin": WEB}
    ) as api:
        await api.post("/session", json={"language": "en"})
        yield api


async def ready_case(api: httpx.AsyncClient) -> str:
    cid: str = (
        await api.post("/cases", json={"language": "en", "jurisdiction": "central"})
    ).json()["id"]
    await api.post(f"/cases/{cid}/questions", json={"text": "Why is our road not built?"})
    await api.put(
        f"/cases/{cid}/authority",
        json={
            "jurisdiction": "central",
            "authority_name": "Example Corporation",
            "pio_address": "Public Information Officer, Example Corporation, Chennai",
        },
    )
    await api.put(
        f"/cases/{cid}/applicant",
        json={"name": NAME, "address": ADDRESS, "phone": None, "bpl": False},
    )
    return cid


async def test_export_is_blocked_until_mandatory_fields_exist(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "en"})).json()["id"]
        response = await api.post(
            f"/cases/{cid}/application", json={"payment_mode": "cash", "place": "Chennai"}
        )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "blocked"
    assert {f["code"] for f in body["detail"]["flags"]} >= {"missing_pio_address", "no_questions"}


async def test_export_renders_stores_and_returns_the_pdf(app: FastAPI) -> None:
    renderer: FakeRenderer = app.state.renderer
    llm: FakeLLM = app.state.llm
    async with signed_in(app) as api:
        cid = await ready_case(api)
        response = await api.post(
            f"/cases/{cid}/application", json={"payment_mode": "cash", "place": "Chennai"}
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

        (doc,) = renderer.documents
        assert (doc.subject, doc.questions) == (COMPOSE.subject, COMPOSE.questions)
        assert (doc.applicant_name, doc.applicant_address) == (NAME, ADDRESS)
        assert doc.pio_address.startswith("Public Information Officer")
        assert (doc.payment_mode, doc.place, doc.bpl, doc.language) == (
            "cash",
            "Chennai",
            False,
            "en",
        )

        compose_call = llm.calls[-1]
        assert compose_call["output"] is Compose
        assert REWRITE.rewritten in compose_call["input"]
        for call in llm.calls:  # golden rule: applicant details never reach the model
            assert NAME not in call["input"] and ADDRESS not in call["input"]

        again = await api.post(
            f"/cases/{cid}/application", json={"payment_mode": "cash", "place": "Chennai"}
        )
        assert again.status_code == 200

    async with app.state.session_factory() as session:
        (document,) = (await session.execute(select(Document))).scalars().all()  # replaced
    stored = path_for(app.state.settings.storage_dir, document.storage_key)
    assert stored.read_bytes() == again.content


async def test_payment_mode_must_come_from_the_rules(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await ready_case(api)
        response = await api.post(
            f"/cases/{cid}/application", json={"payment_mode": "bitcoin", "place": "Chennai"}
        )
    assert (response.status_code, response.json()["error"]) == (400, "invalid_payment_mode")


async def test_deleting_the_case_removes_its_pdf(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await ready_case(api)
        await api.post(f"/cases/{cid}/application", json={"payment_mode": "cash", "place": "X"})
        files = list(app.state.settings.storage_dir.glob("*.pdf"))
        assert len(files) == 1
        await api.delete(f"/cases/{cid}")
    assert not files[0].exists()
