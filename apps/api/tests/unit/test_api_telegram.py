"""POST /telegram/webhook (docs/api.md "Telegram", pentest item 1) and the bot in the API lifespan.

The secret header is checked before the body is parsed or the database touched; a replayed
update is harmless; the bot starts and stops with the app and never takes the API down."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from test_bot_fakes import (
    BOT_TOKEN,
    CHAT_ID,
    CHAT_KEY,
    WEBHOOK_SECRET,
    FakeLLM,
    FakeRenderer,
    FakeRequest,
    bot_settings,
    dispose,
    filed_case,
    make_db,
    reminder_for,
    row_counts,
    use_test_key,
)

from unseal import scheduler
from unseal.api.app import TICK_MINUTES, create_app, start_jobs
from unseal.api.telegram import start_bot, stop_bot
from unseal.bot.texts import t

pytestmark = pytest.mark.anyio

URL = "/telegram/webhook"
HEADER = "X-Telegram-Bot-Api-Secret-Token"


@pytest.fixture(autouse=True)
def _test_key() -> Iterator[None]:
    yield from use_test_key()


async def api_app(
    tmp_path: Path, *, llm: Any = "fake", run_scheduler: bool = True, **overrides: Any
) -> FastAPI:
    settings = bot_settings(tmp_path, **overrides)
    factory = await make_db(settings)
    model = FakeLLM() if llm == "fake" else llm
    return create_app(
        settings,
        session_factory=factory,
        llm=model,
        renderer=FakeRenderer(),
        run_scheduler=run_scheduler,
    )


def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://api.test")


def start_update(update_id: int = 77) -> dict[str, Any]:
    person = {"id": CHAT_ID, "is_bot": False, "first_name": "Test"}
    message = {
        "message_id": 1,
        "date": 1_790_000_000,
        "chat": {"id": CHAT_ID, "type": "private"},
        "from": person,
        "text": "/start",
        "entities": [{"type": "bot_command", "offset": 0, "length": 6}],
    }
    return {"update_id": update_id, "message": message}


async def said(request: FakeRequest, text: str, times: int = 1) -> None:
    """Wait for the running bot (it processes updates in the background) to send `text`."""
    for _ in range(200):
        if request.texts().count(text) >= times:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the bot never sent {text!r} {times} time(s)")


Build = Callable[..., Awaitable[FastAPI]]


@pytest.fixture
async def build(tmp_path: Path) -> AsyncIterator[Build]:
    """Makes apps over one temp DB; stops their bots and closes the engines afterwards."""
    made: list[FastAPI] = []

    async def make(**overrides: Any) -> FastAPI:
        app = await api_app(tmp_path, **overrides)
        made.append(app)
        return app

    yield make
    for app in made:
        await stop_bot(app)
        await dispose(app.state.session_factory)


@pytest.fixture
async def live(build: Build) -> AsyncIterator[tuple[FastAPI, FakeRequest]]:
    app = await build()
    request = FakeRequest()
    await start_bot(app, request=request)
    yield app, request


async def test_404_when_the_bot_is_not_configured(build: Build) -> None:
    app = await build(telegram_bot_token=None)
    async with app.router.lifespan_context(app), client(app) as api:
        response = await api.post(URL, json=start_update(), headers={HEADER: WEBHOOK_SECRET})
    assert (response.status_code, response.json()) == (404, {"error": "not_found"})


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {HEADER: ""},
        {HEADER: "wrong"},
        {HEADER: WEBHOOK_SECRET + "x"},
        {HEADER: "sécret".encode("latin-1")},
    ],
    ids=["missing", "empty", "wrong", "longer", "non-ascii"],
)
async def test_a_bad_secret_is_refused_before_anything_runs(
    live: tuple[FastAPI, FakeRequest], headers: dict[str, Any]
) -> None:
    app, request = live
    async with client(app) as api:
        valid = await api.post(URL, json=start_update(), headers=headers)
        garbage = await api.post(URL, content=b"{not json", headers=headers)
    for response in (valid, garbage):  # the body is never parsed without the secret
        assert (response.status_code, response.json()) == (403, {"error": "bad_secret"})
    await asyncio.sleep(0.05)
    assert [call.endpoint for call in request.calls] == ["getMe"], "no handler ran"
    assert set((await row_counts(app.state.session_factory)).values()) == {0}


async def test_the_right_secret_is_accepted_and_handled(live: tuple[FastAPI, FakeRequest]) -> None:
    app, request = live
    async with client(app) as api:  # no Origin header: the route is exempt from the CSRF check
        response = await api.post(URL, json=start_update(), headers={HEADER: WEBHOOK_SECRET})
    assert (response.status_code, response.content) == (200, b"")
    await said(request, t("choose_language", "en"))


async def test_a_replayed_update_is_harmless(live: tuple[FastAPI, FakeRequest]) -> None:
    app, request = live
    async with client(app) as api:
        first = await api.post(URL, json=start_update(5), headers={HEADER: WEBHOOK_SECRET})
        again = await api.post(URL, json=start_update(5), headers={HEADER: WEBHOOK_SECRET})
        other = await api.post(URL, json=start_update(6), headers={HEADER: WEBHOOK_SECRET})
    assert first.status_code == again.status_code == other.status_code == 200
    await said(request, t("choose_language", "en"), times=2)
    await asyncio.sleep(0.05)
    assert request.texts().count(t("choose_language", "en")) == 2  # updates 5 and 6, once each


@pytest.mark.parametrize(
    "body", [b"{not json", b"[]", b'{"update_id": "7"}', json.dumps({"message": {}}).encode()]
)
async def test_a_malformed_update_is_400(live: tuple[FastAPI, FakeRequest], body: bytes) -> None:
    app, _ = live
    async with client(app) as api:
        response = await api.post(URL, content=body, headers={HEADER: WEBHOOK_SECRET})
    assert (response.status_code, response.json()) == (400, {"error": "invalid"})


async def test_stop_turns_the_webhook_off(live: tuple[FastAPI, FakeRequest]) -> None:
    app, _ = live
    application = app.state.telegram
    assert application.running
    await stop_bot(app)
    assert app.state.telegram is None and not application.running
    async with client(app) as api:
        response = await api.post(URL, json=start_update(), headers={HEADER: WEBHOOK_SECRET})
    assert response.status_code == 404
    await stop_bot(app)  # idempotent


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({"telegram_chat_hash_key": None}, "TELEGRAM_CHAT_HASH_KEY"),
        ({"telegram_webhook_secret": None}, "TELEGRAM_WEBHOOK_SECRET"),
        ({"llm": None}, "model client"),
    ],
)
async def test_incomplete_configuration_leaves_the_bot_off(
    build: Build, caplog: pytest.LogCaptureFixture, overrides: dict[str, Any], missing: str
) -> None:
    app = await build(**overrides)
    request = FakeRequest()
    with caplog.at_level(logging.ERROR):
        await start_bot(app, request=request)
    assert app.state.telegram is None and request.calls == []
    assert missing in caplog.text
    for secret in (BOT_TOKEN, WEBHOOK_SECRET, CHAT_KEY):
        assert secret not in caplog.text
    async with client(app) as api:
        response = await api.post(URL, json=start_update(), headers={HEADER: WEBHOOK_SECRET})
    assert response.status_code == 404


async def test_telegram_being_down_does_not_take_the_api_down(
    build: Build, caplog: pytest.LogCaptureFixture
) -> None:
    app = await build()
    with caplog.at_level(logging.ERROR):
        await start_bot(app, request=FakeRequest(fail_get_me=True))
    assert app.state.telegram is None
    assert "telegram bot disabled" in caplog.text and BOT_TOKEN not in caplog.text


# ---------------------------------------------------------------- the scheduler (FR-9)


class TickRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, factory: object, **kwargs: Any) -> None:
        self.calls.append({"factory": factory, **kwargs})


async def test_the_lifespan_runs_a_tick_every_15_minutes(build: Build) -> None:
    app = await build(telegram_bot_token=None)
    async with app.router.lifespan_context(app):
        jobs = app.state.jobs
        job = jobs.get_job("tick")
        assert jobs.running and TICK_MINUTES == 15
        assert job.trigger.interval == timedelta(minutes=TICK_MINUTES)
        assert (job.max_instances, job.coalesce) == (1, True)
        assert job.next_run_time - datetime.now(UTC) < timedelta(minutes=1)  # soon after start
    await asyncio.sleep(0)  # AsyncIOScheduler.shutdown runs on the next loop iteration
    assert not jobs.running


async def test_the_scheduler_can_stay_off(build: Build) -> None:
    app = await build(telegram_bot_token=None, run_scheduler=False)
    async with app.router.lifespan_context(app):
        assert app.state.jobs is None


async def test_a_tick_without_telegram_claims_no_reminders(
    build: Build, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = TickRecorder()
    monkeypatch.setattr(scheduler, "tick", recorder)
    app = await build(telegram_bot_token=None)
    async with app.router.lifespan_context(app):
        await app.state.jobs.get_job("tick").func()
    [call] = recorder.calls
    assert call["factory"] is app.state.session_factory
    assert call["storage_dir"] == app.state.settings.storage_dir
    assert call["send"] is None
    assert abs(call["now"] - datetime.now(UTC)) < timedelta(minutes=1)


async def test_a_tick_with_telegram_sends_reminders_through_the_bot(
    live: tuple[FastAPI, FakeRequest], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, request = live
    recorder = TickRecorder()
    monkeypatch.setattr(scheduler, "tick", recorder)
    jobs = start_jobs(app)
    try:
        await jobs.get_job("tick").func()
    finally:
        jobs.shutdown(wait=False)
    [call] = recorder.calls
    case = await filed_case(app.state.session_factory, telegram=True, language="en")
    await call["send"](reminder_for(case, "first_appeal", "7d"))
    [sent] = request.sent("sendMessage")
    assert sent.params["chat_id"] == CHAT_ID
    assert t("kind_first_appeal", "en") in sent.params["text"]
