"""FR-1 intake with FR-4 authority suggestions, and the reference-data routes."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import BaseModel

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import ModelBusy, StructuredResult
from unseal.llm.schemas import Intake
from unseal.rules.engine import load_rules

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"


def intake(**changes: Any) -> Intake:
    base: dict[str, Any] = {
        "jurisdiction_hint": "central",
        "authority": "CBSE",
        "time_period": "2026",
        "records_wanted": ["answer book"],
        "delivery_mode": "post",
        "bpl": "unknown",
        "follow_up_questions": ["உங்கள் பதிவு எண் என்ன?"],
        "ready_to_draft": False,
    }
    return Intake.model_validate({**base, **changes})


class FakeLLM:
    def __init__(self, *results: BaseModel | Exception) -> None:
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


async def make_app(tmp_path: Path, *results: BaseModel | Exception) -> FastAPI:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'intake.db').as_posix()}",
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
        await api.post("/session", json={"language": "ta"})
        yield api


async def test_intake_returns_facts_and_curated_authorities(tmp_path: Path) -> None:
    app = await make_app(tmp_path, intake())
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        response = await api.post(f"/cases/{cid}/intake", json={"message": "என் மதிப்பெண் தவறு"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intake"]["follow_up_questions"] == ["உங்கள் பதிவு எண் என்ன?"]
    first = body["authorities"][0]
    assert first["id"] == "cbse-regional-office-chennai"
    assert first["jurisdiction"] == "central" and first["pio_address"]
    assert len(body["authorities"]) <= 3
    call = app.state.llm.calls[0]
    assert call["input"] == "என் மதிப்பெண் தவறு" and call["output"] is Intake
    assert call["reasoning_effort"] == "none" and "Tamil" in call["instructions"]


async def test_intake_falls_back_to_the_records_when_no_authority_is_named(
    tmp_path: Path,
) -> None:
    facts = intake(jurisdiction_hint="tamil_nadu", authority=None, records_wanted=["ration card"])
    app = await make_app(tmp_path, facts)
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        body = (await api.post(f"/cases/{cid}/intake", json={"message": "x"})).json()
    assert body["authorities"][0]["id"] == "civil-supplies-consumer-protection"
    assert all(a["jurisdiction"] == "tamil_nadu" for a in body["authorities"])


async def test_intake_busy_is_busy(tmp_path: Path) -> None:
    app = await make_app(tmp_path, ModelBusy("busy"))
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        response = await api.post(f"/cases/{cid}/intake", json={"message": "x"})
    assert (response.status_code, response.json()) == (503, {"error": "busy"})


async def test_rules_route_serves_values_with_their_sources(tmp_path: Path) -> None:
    app = await make_app(tmp_path)
    central = load_rules("central")
    async with signed_in(app) as api:
        body = (await api.get("/rules/central")).json()
        missing = await api.get("/rules/kerala")
    assert body["application_fee"] == central.local.application_fee.rupees
    assert body["word_limit"] == central.local.word_limit.words  # type: ignore[union-attr]
    assert body["payment_modes"] == list(central.local.payment_modes.modes)
    assert body["bpl_certificate_required"] is True
    pio = next(s for s in body["sources"] if s["rule"] == "act.pio_reply")
    assert pio["source_url"].startswith("https://") and pio["recheck"] is False
    assert missing.status_code == 404


async def test_authorities_route_searches_the_curated_list(tmp_path: Path) -> None:
    app = await make_app(tmp_path)
    async with signed_in(app) as api:
        search = "/authorities/search"
        passport = (await api.post(search, json={"q": "passport"})).json()
        tn_only = (
            await api.post(search, json={"q": "chennai", "jurisdiction": "tamil_nadu"})
        ).json()
        empty = (await api.post(search, json={"q": " "})).json()
        in_url = await api.get("/authorities", params={"q": "passport"})
    assert passport[0]["id"] == "passport-regional-office-chennai"
    assert tn_only and all(a["jurisdiction"] == "tamil_nadu" for a in tn_only)
    assert empty == []
    assert in_url.status_code in (404, 405)  # search text never travels in a URL


async def test_reference_routes_need_a_session(tmp_path: Path) -> None:
    app = await make_app(tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.test") as api:
        assert (await api.get("/rules/central")).status_code == 401
        search = await api.post("/authorities/search", json={"q": "cbse"}, headers={"Origin": WEB})
        assert search.status_code == 401


async def test_an_empty_intake_message_never_reaches_the_model(tmp_path: Path) -> None:
    app = await make_app(tmp_path)
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        response = await api.post(f"/cases/{cid}/intake", json={"message": ""})
    assert response.status_code == 400 and app.state.llm.calls == []


async def test_the_jurisdiction_hint_filters_the_candidates(tmp_path: Path) -> None:
    app = await make_app(tmp_path, intake(jurisdiction_hint="tamil_nadu", authority="chennai"))
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        body = (await api.post(f"/cases/{cid}/intake", json={"message": "x"})).json()
    assert body["authorities"]
    assert all(a["jurisdiction"] == "tamil_nadu" for a in body["authorities"])
