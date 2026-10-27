"""Case routes (docs/api.md "Cases"): FR-2 rewrite, FR-3 validation, FR-6/7 filing and tracking."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import func, select, text

from unseal.api.app import create_app
from unseal.config import Settings
from unseal.db.crypto import set_key_provider
from unseal.db.models import Base, Deadline, Question
from unseal.db.session import build_engine, build_session_factory
from unseal.llm.client import ModelBusy, StructuredResult
from unseal.llm.schemas import Rewrite
from unseal.rules.deadlines import compute_deadlines
from unseal.rules.engine import load_rules

pytestmark = pytest.mark.anyio

WEB = "http://localhost:3000"
REWRITE = Rewrite(
    rewritten="Certified copy of the evaluated answer script for <REG_NO>",
    records_requested=["answer script", "marks per question"],
    reason="Asks for records instead of reasons",
    personal_information=False,
    suggestion=None,
)
REFUSED = Rewrite(
    rewritten="",
    records_requested=[],
    reason="This is another person's personal information",
    personal_information=True,
    suggestion="Ask for the total number of taxpayers in the ward instead",
)


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


async def make_app(tmp_path: Path, llm: FakeLLM | None = None, **overrides: Any) -> FastAPI:
    config = Settings(
        _env_file=None,
        bharatcode_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'cases.db').as_posix()}",
        app_base_url=WEB,
        storage_dir=tmp_path / "storage",
        **overrides,
    )
    engine = build_engine(config.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return create_app(config, session_factory=build_session_factory(engine), llm=llm or FakeLLM())


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    yield await make_app(tmp_path, FakeLLM(REWRITE, REFUSED))


@asynccontextmanager
async def signed_in(app: FastAPI, language: str = "ta") -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    headers = {"Origin": WEB}
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.test", headers=headers
    ) as api:
        await api.post("/session", json={"language": language})
        yield api


async def new_case(api: httpx.AsyncClient, **body: Any) -> dict[str, Any]:
    response = await api.post("/cases", json={"language": "ta", "jurisdiction": "central", **body})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_create_list_get_and_ownership(app: FastAPI) -> None:
    async with signed_in(app) as api, signed_in(app, "en") as other:
        case = await new_case(api)
        assert (case["status"], case["language"], case["questions"], case["deadlines"]) == (
            "draft",
            "ta",
            [],
            [],
        )
        listed = (await api.get("/cases")).json()
        assert [c["id"] for c in listed] == [case["id"]] and listed[0]["next_deadline"] is None
        assert (await api.get(f"/cases/{case['id']}")).json()["id"] == case["id"]
        stranger = await other.get(f"/cases/{case['id']}")
        assert (stranger.status_code, stranger.json()) == (404, {"error": "not_found"})
        assert (await other.get("/cases")).json() == []
        assert (await api.get("/cases/not-a-uuid")).status_code == 404


async def test_question_rewrite_accept_edit_and_delete(app: FastAPI) -> None:
    llm: FakeLLM = app.state.llm
    async with signed_in(app) as api:
        case = await new_case(api)
        created = await api.post(f"/cases/{case['id']}/questions", json={"text": "ஏன் குறைவு?"})
        assert created.status_code == 201
        question = created.json()
        assert question["original_text"] == "ஏன் குறைவு?"
        assert question["rewritten_text"] == REWRITE.rewritten
        assert question["records_requested"] == REWRITE.records_requested
        assert question["reason"] == REWRITE.reason and question["accepted"] is False
        assert llm.calls[0]["input"] == "ஏன் குறைவு?" and "Tamil" in llm.calls[0]["instructions"]

        url = f"/cases/{case['id']}/questions/{question['id']}"
        edited = (await api.patch(url, json={"rewritten_text": "Copy of the answer script"})).json()
        assert edited["rewritten_text"] == "Copy of the answer script"
        assert (await api.patch(url, json={"accepted": True})).json()["accepted"] is True

        refused = (await api.post(f"/cases/{case['id']}/questions", json={"text": "x"})).json()
        assert refused["personal_information"] is True and refused["suggestion"]
        assert refused["position"] == 2
        assert (await api.delete(url)).status_code == 204
        positions = [
            q["position"] for q in (await api.get(f"/cases/{case['id']}")).json()["questions"]
        ]
        assert positions == [2]


async def test_question_text_is_encrypted_at_rest(app: FastAPI) -> None:
    async with signed_in(app) as api:
        case = await new_case(api)
        await api.post(f"/cases/{case['id']}/questions", json={"text": "Register TEST-0042 marks"})
    async with app.state.session_factory() as session:
        raw = (await session.execute(text("SELECT original_text FROM questions"))).scalar_one()
        assert "TEST-0042" not in raw


async def test_model_busy_reaches_the_client_as_busy(tmp_path: Path) -> None:
    app = await make_app(tmp_path, FakeLLM(ModelBusy("busy")))
    async with signed_in(app) as api:
        case = await new_case(api)
        response = await api.post(f"/cases/{case['id']}/questions", json={"text": "why?"})
    assert (response.status_code, response.json()) == (503, {"error": "busy"})
    async with app.state.session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Question))).scalar_one() == 0


async def test_model_routes_have_their_own_quota(tmp_path: Path) -> None:
    app = await make_app(tmp_path, FakeLLM(REWRITE, REWRITE), rate_limit_model="1/minute")
    async with signed_in(app) as api:
        case = await new_case(api)
        first = await api.post(f"/cases/{case['id']}/questions", json={"text": "why?"})
        second = await api.post(f"/cases/{case['id']}/questions", json={"text": "why?"})
    assert first.status_code == 201
    assert (second.status_code, second.json()) == (429, {"error": "rate_limited"})


async def test_validation_blocks_until_addresses_exist(app: FastAPI) -> None:
    async with signed_in(app) as api:
        case = await new_case(api)
        cid = case["id"]
        flags = (await api.get(f"/cases/{cid}/validation")).json()["flags"]
        assert {f["code"] for f in flags} == {
            "missing_pio_address",
            "missing_applicant_address",
            "no_questions",
        }
        await api.post(f"/cases/{cid}/questions", json={"text": "why?"})
        await api.put(
            f"/cases/{cid}/authority",
            json={
                "jurisdiction": "central",
                "authority_name": "Example Board",
                "pio_address": "Public Information Officer, Example Board, New Delhi",
                "via_apio": False,
                "third_party": False,
                "life_liberty": False,
            },
        )
        applicant = {
            "name": "Test Applicant",
            "address": "1 Sample Road",
            "phone": None,
            "bpl": False,
        }
        assert (await api.put(f"/cases/{cid}/applicant", json=applicant)).status_code == 204
        assert (await api.get(f"/cases/{cid}/validation")).json()["flags"] == []
        body = (await api.get(f"/cases/{cid}")).json()
        assert body["has_applicant"] is True and "Test Applicant" not in str(body)


async def test_filing_creates_engine_deadlines_and_moves_to_reply_due(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await new_case(api))["id"]
        filed = await api.post(
            f"/cases/{cid}/filing", json={"filed_on": "2026-10-27", "filing_mode": "post"}
        )
        again = await api.post(
            f"/cases/{cid}/filing", json={"filed_on": "2026-10-28", "filing_mode": "post"}
        )
    assert filed.status_code == 200
    case = filed.json()
    expected = compute_deadlines(
        filed_on=date(2026, 10, 27),
        received_on=None,
        via_apio=False,
        third_party=False,
        life_liberty=False,
        rules=load_rules("central"),
    )
    by_kind = {d["kind"]: d for d in case["deadlines"]}
    assert case["status"] == "reply_due" and case["received_estimated"] is True
    assert by_kind["pio_reply"]["due_on"] == expected.pio_reply.due_on.isoformat()
    assert by_kind["pio_reply"]["estimated"] is True
    assert by_kind["first_appeal"]["due_on"] == expected.first_appeal.due_on.isoformat()
    assert (again.status_code, again.json()["error"]) == (409, "wrong_status")


async def test_reply_and_close_follow_the_lifecycle(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await new_case(api))["id"]
        early = await api.post(f"/cases/{cid}/reply", json={"received_on": "2026-11-20"})
        assert (early.status_code, early.json()["error"]) == (409, "wrong_status")
        await api.post(
            f"/cases/{cid}/filing",
            json={"filed_on": "2026-10-27", "filing_mode": "post", "received_on": "2026-10-29"},
        )
        replied = (await api.post(f"/cases/{cid}/reply", json={"received_on": "2026-11-20"})).json()
        first_appeal = next(d for d in replied["deadlines"] if d["kind"] == "first_appeal")
        assert replied["status"] == "replied" and first_appeal["due_on"] == "2026-12-20"
        closed = (await api.post(f"/cases/{cid}/close")).json()
        assert closed["status"] == "closed"
        listed = (await api.get("/cases")).json()
        assert listed[0]["status"] == "closed"


async def test_delete_case_removes_rows(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await new_case(api))["id"]
        await api.post(f"/cases/{cid}/questions", json={"text": "why?"})
        await api.post(
            f"/cases/{cid}/filing", json={"filed_on": "2026-10-27", "filing_mode": "post"}
        )
        assert (await api.delete(f"/cases/{cid}")).status_code == 204
        assert (await api.get(f"/cases/{cid}")).status_code == 404
    async with app.state.session_factory() as session:
        for model in (Question, Deadline):
            assert (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one() == 0


async def test_export_includes_case_details(app: FastAPI) -> None:
    async with signed_in(app) as api:
        cid = (await new_case(api))["id"]
        await api.put(
            f"/cases/{cid}/applicant",
            json={"name": "Test Applicant", "address": "1 Sample Road", "phone": None, "bpl": True},
        )
        await api.post(f"/cases/{cid}/questions", json={"text": "why?"})
        exported = (await api.get("/me/export")).json()
    (case,) = exported["cases"]
    assert case["applicant"] == {
        "name": "Test Applicant",
        "address": "1 Sample Road",
        "phone": None,
        "bpl": True,
    }
    assert case["questions"][0]["original_text"] == "why?"
