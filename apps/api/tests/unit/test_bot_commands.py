"""/cases, /delete (FR-8), stale buttons, service errors, per-chat quota and the non-blocking
production mode of the Telegram bot."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from test_bot_fakes import (
    ADDRESS,
    NAME,
    UNIVERSITY,
    FakeIntake,
    FakeLLM,
    Harness,
    intake_result,
    start_harness,
    use_test_key,
)

from unseal.api.telegram import RecentUpdates
from unseal.bot import finish
from unseal.bot.texts import t
from unseal.db.models import Case, User
from unseal.harness.validate import Flag
from unseal.llm.client import ModelBusy, ModelIncomplete
from unseal.llm.schemas import Compose, Rewrite
from unseal.pdf.labels import labels_for
from unseal.services import cases as case_service
from unseal.services import intake as intake_service

pytestmark = pytest.mark.anyio

REWRITE = Rewrite(
    rewritten="Certified copy of the work order for the ward road",
    records_requested=["work order"],
    reason="Asks for records instead of reasons",
    personal_information=False,
    suggestion=None,
)
COMPOSE = Compose(subject="Ward road work order", questions=[REWRITE.rewritten])


@pytest.fixture(autouse=True)
def _test_key() -> Iterator[None]:
    yield from use_test_key()


@pytest.fixture
async def h(tmp_path: Path) -> AsyncIterator[Harness]:
    harness = await start_harness(tmp_path, FakeLLM(REWRITE, COMPOSE))
    yield harness
    await harness.close()


def fake_intake(monkeypatch: pytest.MonkeyPatch, *results: object) -> FakeIntake:
    fake = FakeIntake(*results)  # type: ignore[arg-type]
    monkeypatch.setattr(intake_service, "run_intake", fake)
    return fake


async def to_review(h: Harness, monkeypatch: pytest.MonkeyPatch, language: str = "en") -> None:
    fake_intake(monkeypatch, intake_result())
    label = {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}[language]
    await h.chat.send("/start")
    await h.chat.press(label)
    await h.chat.press(t("agree", language))
    await h.chat.send("Why is our ward road still not built?")
    await h.chat.press(UNIVERSITY["name_ta"] if language == "ta" else UNIVERSITY["name"])
    await h.chat.press(t("confirm", language))


async def to_pdf(h: Harness, monkeypatch: pytest.MonkeyPatch, language: str = "en") -> None:
    await to_review(h, monkeypatch, language)
    await h.chat.press(t("done", language))
    await h.chat.send(NAME)
    await h.chat.send(ADDRESS)
    await h.chat.press(t("no", language))
    await h.chat.press(labels_for(language).payment_modes["cash"])  # type: ignore[arg-type]
    assert h.request.last_text() == t("ask_place", language)
    await h.chat.send("Chennai")


async def test_cases_and_delete_store_nothing_for_a_stranger(h: Harness) -> None:
    await h.chat.send("/cases")
    assert h.request.last_text() == t("no_cases", "en")
    await h.chat.send("/delete")
    assert h.request.last_text() == t("nothing_stored", "en")
    await h.chat.tap("del:yes")
    assert set((await h.counts()).values()) == {0}


async def test_cases_lists_a_draft_without_a_deadline(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    await to_review(h, monkeypatch, "hi")
    await h.chat.send("/cases")
    line = t("case_line", "hi", n=1, authority=UNIVERSITY["name"], status=t("status_draft", "hi"))
    assert h.request.last_text() == t("cases_header", "hi") + "\n" + line  # no deadline yet


async def test_delete_removes_every_row_and_file(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    await to_pdf(h, monkeypatch, "ta")
    storage = h.settings.storage_dir
    assert len(list(storage.iterdir())) == 1
    counts = await h.counts()
    assert all(counts[table] >= 1 for table in ("users", "applicants", "cases", "questions"))
    assert counts["documents"] == 1

    await h.chat.send("/delete")
    assert h.request.last_text() == t("delete_confirm", "ta")
    await h.chat.press(t("delete_no", "ta"))
    assert h.request.last_text() == t("kept", "ta")
    assert await h.counts() == counts

    await h.chat.send("/delete")
    await h.chat.press(t("delete_yes", "ta"))
    assert h.request.last_text() == t("deleted", "ta")
    assert set((await h.counts()).values()) == {0}
    assert list(storage.iterdir()) == []

    await h.chat.send("/cases")  # the language went with the data
    assert h.request.last_text() == t("no_cases", "en")


async def test_delete_mid_conversation_ends_it(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    await to_review(h, monkeypatch)
    await h.chat.send("/delete")
    await h.chat.press(t("delete_yes", "en"))
    assert set((await h.counts()).values()) == {0}
    await h.chat.tap("q:done")  # an old button after deletion
    assert h.request.answers()[-1] == t("need_start", "en")


async def test_outside_a_conversation_the_bot_points_to_start(h: Harness) -> None:
    await h.chat.send("hello")
    assert h.request.last_text() == t("need_start", "en")
    await h.chat.tap("q:accept:00000000-0000-4000-8000-000000000000")
    assert h.request.answers()[-1] == t("need_start", "en")
    assert set((await h.counts()).values()) == {0}


async def test_a_vanished_case_is_reported_not_crashed(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    await to_review(h, monkeypatch)
    async with h.factory() as session:
        await session.execute(delete(Case))
        await session.commit()
    question_button = h.chat.button(t("accept", "en"))
    await h.chat.tap(question_button)
    assert h.request.last_text() == t("not_found", "en")


async def test_a_blocked_export_lists_what_is_missing(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def blocked(*_: object, **__: object) -> bytes:
        raise case_service.Blocked(
            [
                Flag(code="missing_pio_address", severity="block"),
                Flag(code="missing_applicant_address", severity="block"),
            ]
        )

    monkeypatch.setattr(case_service, "build_application", blocked)
    await to_pdf(h, monkeypatch)
    items = "\n".join(
        "- " + t(key, "en")
        for key in ("flag_missing_pio_address", "flag_missing_applicant_address")
    )
    assert h.request.last_text() == t("blocked", "en", items=items)
    assert [label for label, _ in h.request.buttons()] == [t("add", "en")]


async def test_model_calls_are_metered_per_chat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = await start_harness(tmp_path, FakeLLM(REWRITE), rate_limit_model="1/minute")
    try:
        await to_review(h, monkeypatch)  # the intake call uses the one allowed call
        assert h.request.last_text() == t("rate_limited", "en")
        assert h.llm.calls == []
    finally:
        await h.close()


async def test_production_mode_does_not_block_and_answers_while_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = asyncio.Event()

    async def slow_intake(llm: object, message: str, *, language: str) -> object:
        await release.wait()
        return intake_result()

    monkeypatch.setattr(intake_service, "run_intake", slow_intake)
    h = await start_harness(tmp_path, FakeLLM(), block=False)
    await h.application.start()  # as in the API: non-blocking handlers run as app tasks
    try:

        async def settle(expected: str) -> None:
            for _ in range(200):
                if h.request.texts() and h.request.last_text() == expected:
                    return
                await asyncio.sleep(0.01)
            raise AssertionError(f"bot never said {expected!r}; last: {h.request.texts()[-1:]}")

        await h.chat.send("/start")
        await settle(t("choose_language", "en"))
        await h.chat.press("English")
        await settle(t("privacy", "en"))
        await h.chat.press(t("agree", "en"))
        await settle(t("describe", "en"))
        await h.chat.send("Why is our ward road still not built?")
        await settle(t("working", "en"))
        await h.chat.send("hello?")  # while the model is still thinking
        await settle(t("still_working", "en"))
        release.set()
        await settle(t("choose_authority", "en"))
    finally:
        await h.close()


async def test_user_language_survives_a_restart(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    await to_review(h, monkeypatch, "ta")
    h.application.drop_user_data(h.chat.chat_id)  # what a process restart does to memory
    await h.chat.send("/cases")
    assert h.request.last_text().startswith(t("cases_header", "ta"))
    async with h.factory() as session:
        assert (await session.execute(select(User.language))).scalar_one() == "ta"


async def test_retry_works_at_the_question_and_application_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = FakeLLM(
        ModelBusy("busy"), REWRITE, ModelIncomplete("max_output_tokens", "partial"), COMPOSE
    )
    h = await start_harness(tmp_path, llm)
    try:
        await to_review(h, monkeypatch)
        assert h.request.last_text() == t("busy", "en")
        await h.chat.press(t("retry", "en"))
        assert h.request.last_text().startswith(
            t("rewritten", "en", text=REWRITE.rewritten, reason=REWRITE.reason)
        )
        await h.chat.press(t("done", "en"))
        await h.chat.send(NAME)
        await h.chat.send(ADDRESS)
        await h.chat.press(t("no", "en"))
        await h.chat.press(labels_for("en").payment_modes["cash"])
        await h.chat.send("Chennai")
        assert h.request.last_text() == t("incomplete", "en")
        assert h.request.sent("sendDocument") == []
        await h.chat.press(t("retry", "en"))
        assert len(h.request.sent("sendDocument")) == 1
        assert h.request.last_text() == t("ask_filed", "en")
        await h.chat.tap("retry")  # nothing pending any more
        assert h.request.answers()[-1] == "" and h.request.last_text() == t("stale", "en")
    finally:
        await h.close()


async def test_input_is_capped_and_stray_buttons_are_ignored(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = fake_intake(monkeypatch, intake_result())
    await h.chat.send("/start")
    await h.chat.press("English")
    await h.chat.tap("bpl:yes")  # a button from another step
    assert h.request.answers()[-1] == t("stale", "en")
    await h.chat.press(t("agree", "en"))
    await h.chat.send("   ")
    assert h.request.last_text() == t("empty", "en")
    await h.chat.send("x" * 2001)
    assert h.request.last_text() == t("too_long", "en", limit=2000)
    assert intake.calls == []
    await h.chat.send("Why is our ward road still not built?")
    await h.chat.tap("auth:7")  # no such candidate: the list is shown again
    assert h.request.last_text() == t("choose_authority", "en")


async def test_filing_twice_is_reported(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    async def already_filed(*_: object, **__: object) -> None:
        raise case_service.WrongStatus

    await to_pdf(h, monkeypatch)
    monkeypatch.setattr(finish, "file_case", already_filed)
    await h.chat.send("today")
    await h.chat.press(t("mode_post", "en"))
    assert h.request.last_text() == t("wrong_status", "en")


def test_redelivery_window_forgets_the_oldest_ids() -> None:
    seen = RecentUpdates(size=2)
    assert [seen.first_time(i) for i in (1, 2, 1, 3)] == [True, True, False, True]
    assert seen.first_time(1) is True  # 1 fell out of the window when 3 arrived


async def test_nothing_personal_reaches_the_logs_even_at_debug(
    h: Harness, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        await to_pdf(h, monkeypatch)
        await h.chat.send("today")
        await h.chat.press(t("mode_post", "en"))
    assert h.request.sent("sendDocument")  # the flow really ran
    for secret in (
        NAME,
        ADDRESS,
        "ward road",
        str(h.chat.chat_id),
        h.settings.telegram_chat_hash_key.get_secret_value(),
    ):
        assert secret not in caplog.text
