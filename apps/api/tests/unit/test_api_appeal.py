"""First appeal (FR-10, S. 19(1)): the draft PDF and recording that the appeal was filed."""

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
from unseal.llm.client import StructuredResult
from unseal.llm.schemas import Rewrite
from unseal.pdf.models import AppealDocument
from unseal.rules.deadlines import faa_decision_deadlines, second_appeal_deadline
from unseal.rules.engine import load_rules

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"
TODAY = date(2026, 10, 20)
REWRITE = Rewrite(
    rewritten="Certified copy of the evaluated answer script",
    records_requested=["answer script"],
    reason="Asks for records",
    personal_information=False,
    suggestion=None,
)
APPEAL = {"grounds": ["incomplete"], "faa_address": "First Appellate Authority\nExample Office"}


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        return StructuredResult(REWRITE, "req-1", 0, False)


class FakeRenderer:
    def __init__(self) -> None:
        self.documents: list[AppealDocument] = []

    def __call__(self, document: AppealDocument) -> bytes:
        self.documents.append(document)
        return b"%PDF-1.7 appeal"


@pytest.fixture(autouse=True)
def encryption_key() -> Iterator[None]:
    key = Fernet.generate_key().decode()
    set_key_provider(lambda: key)
    yield
    set_key_provider(None)


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("unseal.services.appeals.today_ist", lambda: TODAY)


@pytest.fixture
async def app(tmp_path: Path) -> FastAPI:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'appeal.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
    )
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app(config, session_factory=build_session_factory(engine), llm=FakeLLM())
    app.state.appeal_renderer = FakeRenderer()
    return app


@asynccontextmanager
async def signed_in(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test", headers={"Origin": WEB}
    ) as api:
        await api.post("/session", json={"language": "ta"})
        yield api


async def filed_case(api: httpx.AsyncClient, *, applicant: bool = True) -> str:
    cid: str = (
        await api.post("/cases", json={"language": "ta", "jurisdiction": "central"})
    ).json()["id"]
    await api.put(
        f"/cases/{cid}/authority",
        json={
            "jurisdiction": "central",
            "authority_name": "Example Board",
            "pio_address": "PIO, Example Board, Chennai 600001",
        },
    )
    if applicant:
        await api.put(
            f"/cases/{cid}/applicant",
            json={"name": "Test Appellant", "address": "1 Sample Street, Chennai 600002"},
        )
    await api.post(f"/cases/{cid}/questions", json={"text": "why were my marks low"})
    await api.post(
        f"/cases/{cid}/filing",
        json={"filed_on": "2026-08-03", "filing_mode": "post", "received_on": "2026-08-08"},
    )
    return cid


async def test_a_reply_date_is_kept_on_the_case(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        case = (await api.post(f"/cases/{cid}/reply", json={"received_on": "2026-09-01"})).json()
    assert case["reply_received_on"] == "2026-09-01" and case["appeal_filed_on"] is None


async def test_the_appeal_draft_cites_the_case_dates_and_the_picked_grounds(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        await api.post(f"/cases/{cid}/reply", json={"received_on": "2026-09-30"})
        response = await api.post(
            f"/cases/{cid}/appeal",
            json={**APPEAL, "grounds": ["incomplete", "refused"], "details": "Page 2 missing"},
        )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.7 appeal"
    doc = app.state.appeal_renderer.documents[0]
    assert (doc.language, doc.jurisdiction, doc.filing_mode) == ("ta", "central", "post")
    assert (doc.filed_on, doc.received_on) == (date(2026, 8, 3), date(2026, 8, 8))
    assert doc.received_estimated is False
    assert (doc.reply_due_on, doc.reply_received_on) == (date(2026, 9, 7), date(2026, 9, 30))
    assert doc.grounds == ["incomplete", "refused"] and doc.details == "Page 2 missing"
    assert (doc.appellant_name, doc.authority_name) == ("Test Appellant", "Example Board")
    assert doc.faa_address == APPEAL["faa_address"] and doc.prepared_on == TODAY
    assert doc.late is False  # the window runs 30 days from the reply, to 2026-10-30
    assert [c["output"] for c in app.state.llm.calls] == [Rewrite]  # no model writes the appeal


async def test_a_draft_case_cannot_be_appealed(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await api.post("/cases", json={"language": "ta"})).json()["id"]
        response = await api.post(f"/cases/{cid}/appeal", json=APPEAL)
        filing = await api.post(f"/cases/{cid}/appeal/filing", json={"filed_on": "2026-10-10"})
    assert (response.status_code, response.json()) == (409, {"error": "wrong_status"})
    assert (filing.status_code, filing.json()) == (409, {"error": "wrong_status"})


async def test_no_reply_is_not_a_ground_once_a_reply_came(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        await api.post(f"/cases/{cid}/reply", json={"received_on": "2026-09-30"})
        response = await api.post(f"/cases/{cid}/appeal", json={**APPEAL, "grounds": ["no_reply"]})
    assert (response.status_code, response.json()) == (400, {"error": "invalid_grounds"})


async def test_repeated_grounds_are_invalid(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        body = {**APPEAL, "grounds": ["refused", "refused"]}
        response = await api.post(f"/cases/{cid}/appeal", json=body)
    assert response.status_code == 400 and response.json()["error"] == "invalid"


async def test_a_deemed_refusal_appeal_past_the_window_is_marked_late(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)  # PIO due 2026-09-07, first appeal due 2026-10-07
        async with app.state.session_factory() as session:
            await session.execute(update(Case).values(status="deemed_refused"))
            await session.commit()
        body = {**APPEAL, "grounds": ["no_reply"], "delay_reason": "I was in hospital"}
        response = await api.post(f"/cases/{cid}/appeal", json=body)
    assert response.status_code == 200, response.text
    doc = app.state.appeal_renderer.documents[0]
    assert doc.reply_received_on is None and doc.grounds == ["no_reply"]
    assert doc.late is True and doc.delay_reason == "I was in hospital"


async def test_an_overdue_reply_can_be_appealed_before_the_nightly_job_runs(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)  # still reply_due, but the PIO's day has passed
        response = await api.post(f"/cases/{cid}/appeal", json={**APPEAL, "grounds": ["no_reply"]})
    assert response.status_code == 200, response.text


async def test_the_appeal_needs_the_appellant(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api, applicant=False)
        response = await api.post(f"/cases/{cid}/appeal", json={**APPEAL, "grounds": ["no_reply"]})
    assert response.status_code == 409 and response.json()["error"] == "blocked"
    codes = [flag["code"] for flag in response.json()["detail"]["flags"]]
    assert codes == ["missing_applicant_address"]


async def test_one_stored_copy_of_the_appeal(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        for _ in range(2):
            await api.post(f"/cases/{cid}/appeal", json={**APPEAL, "grounds": ["no_reply"]})
    async with app.state.session_factory() as session:
        kinds = list((await session.execute(select(Document.kind))).scalars())
    assert kinds == ["first_appeal"]


async def test_filing_the_appeal_starts_the_faa_and_second_appeal_clocks(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = await filed_case(api)
        body = {"filed_on": "2026-10-10", "received_on": "2026-10-12"}
        case = (await api.post(f"/cases/{cid}/appeal/filing", json=body)).json()
        again = await api.post(f"/cases/{cid}/appeal/filing", json=body)
    rules = load_rules("central")
    faa = faa_decision_deadlines(
        rules=rules, appeal_filed_on=date(2026, 10, 10), appeal_received_on=date(2026, 10, 12)
    )
    second = second_appeal_deadline(faa, rules=rules)
    by_kind = {d["kind"]: d for d in case["deadlines"]}
    assert case["status"] == "appealed" and case["appeal_filed_on"] == "2026-10-10"
    assert by_kind["faa_decision"]["due_on"] == faa.decision.due_on.isoformat()
    assert by_kind["second_appeal"]["due_on"] == second.due_on.isoformat()
    assert (again.status_code, again.json()) == (409, {"error": "wrong_status"})
