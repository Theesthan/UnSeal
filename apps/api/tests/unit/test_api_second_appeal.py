"""Second appeal (FR-12, S. 19(3)) and recording the appellate authority's decision."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy import select, update

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, Case, Document
from unseal.db.session import build_engine, build_session_factory
from unseal.pdf.models import SecondAppealDocument
from unseal.rules.deadlines import faa_decision_deadlines, second_appeal_deadline
from unseal.rules.engine import load_rules

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"
SECOND = {"grounds": ["no_decision"], "faa_address": "First Appellate Authority, Example Board"}


class FakeRenderer:
    def __init__(self) -> None:
        self.documents: list[SecondAppealDocument] = []

    def __call__(self, document: SecondAppealDocument) -> bytes:
        self.documents.append(document)
        return b"%PDF-1.7 second appeal"


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


def pin_today(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    monkeypatch.setattr("unseal.services.appeals.today_ist", lambda: day)


@pytest.fixture(autouse=True)
def default_today(monkeypatch: pytest.MonkeyPatch) -> None:
    pin_today(monkeypatch, date(2026, 10, 20))


@pytest.fixture
async def app(tmp_path: Path) -> FastAPI:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'second.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
    )
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app(config, session_factory=build_session_factory(engine), llm=None)
    app.state.second_appeal_renderer = FakeRenderer()
    return app


@asynccontextmanager
async def signed_in(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test", headers={"Origin": WEB}
    ) as api:
        await api.post("/session", json={"language": "en"})
        yield api


async def appealed_case(app: FastAPI, api: httpx.AsyncClient, jurisdiction: str = "central") -> str:
    """Filed 2026-05-04, received 2026-05-08, no reply; first appeal filed 2026-06-20."""
    body: dict[str, Any] = {"language": "en", "jurisdiction": jurisdiction}
    cid: str = (await api.post("/cases", json=body)).json()["id"]
    authority = {
        "jurisdiction": jurisdiction,
        "authority_name": "Example Board",
        "pio_address": "PIO, Example Board, Chennai 600001",
    }
    await api.put(f"/cases/{cid}/authority", json=authority)
    applicant = {"name": "Test Appellant", "address": "1 Sample Street", "phone": "9000000000"}
    await api.put(f"/cases/{cid}/applicant", json=applicant)
    filing = {"filed_on": "2026-05-04", "filing_mode": "post", "received_on": "2026-05-08"}
    await api.post(f"/cases/{cid}/filing", json=filing)
    async with app.state.session_factory() as session:
        await session.execute(update(Case).values(status="deemed_refused"))
        await session.commit()
    response = await api.post(f"/cases/{cid}/appeal/filing", json={"filed_on": "2026-06-20"})
    assert response.status_code == 200, response.text
    return cid


async def test_too_early_while_the_appellate_authority_still_has_time(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_today(monkeypatch, date(2026, 8, 4))  # the 45-day outer limit is 2026-08-04
    async with signed_in(app) as api:
        cid = await appealed_case(app, api)
        response = await api.post(f"/cases/{cid}/second-appeal", json=SECOND)
    assert response.status_code == 409
    assert response.json() == {"error": "too_early", "detail": {"earliest": "2026-08-05"}}


async def test_no_decision_second_appeal_cites_the_whole_history(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await appealed_case(app, api)
        response = await api.post(
            f"/cases/{cid}/second-appeal",
            json={**SECOND, "grounds": ["no_decision", "no_reply"], "details": "Nothing came"},
        )
    assert response.status_code == 200, response.text
    assert response.content == b"%PDF-1.7 second appeal"
    doc = app.state.second_appeal_renderer.documents[0]
    assert (doc.filed_on, doc.received_on, doc.reply_due_on) == (
        date(2026, 5, 4),
        date(2026, 5, 8),
        date(2026, 6, 7),
    )
    assert doc.reply_received_on is None and doc.faa_decision_received_on is None
    assert doc.appeal_filed_on == date(2026, 6, 20) and doc.appellant_phone == "9000000000"
    assert doc.grounds == ["no_decision", "no_reply"] and doc.details == "Nothing came"
    assert doc.late is False  # no order: due 90 days after the order's due date, 2026-10-25
    assert doc.hearing_mode is None and doc.jurisdiction == "central"


async def test_recording_the_decision_moves_the_second_appeal_deadline(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await appealed_case(app, api)
        early = await api.post(f"/cases/{cid}/appeal/decision", json={"received_on": "2026-06-19"})
        case = (
            await api.post(f"/cases/{cid}/appeal/decision", json={"received_on": "2026-07-10"})
        ).json()
        refused = await api.post(f"/cases/{cid}/second-appeal", json=SECOND)
        late = await api.post(
            f"/cases/{cid}/second-appeal",
            json={**SECOND, "grounds": ["incomplete"], "delay_reason": "Illness"},
        )
    rules = load_rules("central")
    faa = faa_decision_deadlines(rules=rules, appeal_filed_on=date(2026, 6, 20))
    expected = second_appeal_deadline(faa, rules=rules, decision_received_on=date(2026, 7, 10))
    by_kind = {d["kind"]: d for d in case["deadlines"]}
    assert (early.status_code, early.json()["error"]) == (400, "invalid")
    assert case["faa_decision_received_on"] == "2026-07-10"
    assert by_kind["second_appeal"]["due_on"] == expected.due_on.isoformat() == "2026-10-08"
    assert (refused.status_code, refused.json()) == (400, {"error": "invalid_grounds"})
    assert late.status_code == 200, late.text
    doc = app.state.second_appeal_renderer.documents[0]
    assert doc.faa_decision_received_on == date(2026, 7, 10)
    assert doc.late is True and doc.delay_reason == "Illness"


async def test_the_decision_is_recorded_only_on_an_appealed_case(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "en"})).json()["id"]
        response = await api.post(
            f"/cases/{cid}/appeal/decision", json={"received_on": "2026-07-10"}
        )
        second = await api.post(f"/cases/{cid}/second-appeal", json=SECOND)
    assert (response.status_code, response.json()) == (409, {"error": "wrong_status"})
    assert (second.status_code, second.json()) == (409, {"error": "wrong_status"})


async def test_a_tamil_nadu_appeal_carries_the_hearing_mode(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await appealed_case(app, api, jurisdiction="tamil_nadu")
        body = {**SECOND, "hearing_mode": "virtual"}
        response = await api.post(f"/cases/{cid}/second-appeal", json=body)
    assert response.status_code == 200, response.text
    doc = app.state.second_appeal_renderer.documents[0]
    assert doc.jurisdiction == "tamil_nadu" and doc.hearing_mode == "virtual"


async def test_one_stored_copy_of_the_second_appeal(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await appealed_case(app, api)
        for _ in range(2):
            await api.post(f"/cases/{cid}/second-appeal", json=SECOND)
    async with app.state.session_factory() as session:
        kinds = list((await session.execute(select(Document.kind))).scalars())
    assert kinds == ["second_appeal"]
