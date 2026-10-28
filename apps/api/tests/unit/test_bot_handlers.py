"""The Telegram conversation (FR-1 on Telegram, the 90-second demo): driven offline through a real
python-telegram-bot Application, a recording Bot API fake, a fake model and a temp SQLite DB."""

from collections.abc import AsyncIterator, Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
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

from unseal.bot.texts import format_date, t
from unseal.db.models import Applicant, Case, Question, User
from unseal.llm.client import ModelBusy, ModelIncomplete, ModelOutputInvalid
from unseal.llm.schemas import Compose, Rewrite
from unseal.pdf.labels import labels_for
from unseal.rules.engine import load_rules
from unseal.services import cases as case_service
from unseal.services import intake as intake_service

pytestmark = pytest.mark.anyio

TODAY = date(2026, 10, 27)
CONCERN_TA = "என் செமஸ்டர் முடிவு தவறாகத் தெரிகிறது; என் விடைத்தாளைப் பார்க்க வேண்டும்."
FOLLOW_UPS_TA = ["எந்தப் பாடத்தின் விடைத்தாள்?", "எந்தத் தேர்வு அமர்வு?", "மூன்றாவது கேள்வி?"]
REWRITE_TA = Rewrite(
    rewritten="கணிதம் பாடத்தின் மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் சான்றளிக்கப்பட்ட நகல்",
    records_requested=["விடைத்தாள்"],
    reason="காரணத்திற்குப் பதிலாக ஆவணத்தைக் கோருகிறது",
    personal_information=False,
    suggestion=None,
)
COMPOSE_TA = Compose(subject="விடைத்தாள் நகல் கோருதல்", questions=[REWRITE_TA.rewritten])
REWRITE_EN = Rewrite(
    rewritten="Certified copy of the work order for the ward road",
    records_requested=["work order"],
    reason="Asks for records instead of reasons",
    personal_information=False,
    suggestion=None,
)
REFUSED_EN = Rewrite(
    rewritten="",
    records_requested=[],
    reason="This is another person's personal information",
    personal_information=True,
    suggestion="Ask for the number of road contracts given in the ward instead",
)
COMPOSE_EN = Compose(subject="Ward road work order", questions=[REWRITE_EN.rewritten])


@pytest.fixture(autouse=True)
def _test_key() -> Iterator[None]:
    yield from use_test_key()


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(case_service, "today_ist", lambda: TODAY)


@pytest.fixture
async def h(tmp_path: Path) -> AsyncIterator[Harness]:
    harness = await start_harness(tmp_path, FakeLLM(REWRITE_TA, COMPOSE_TA))
    yield harness
    await harness.close()


def fake_intake(monkeypatch: pytest.MonkeyPatch, *results: object) -> FakeIntake:
    fake = FakeIntake(*results)  # type: ignore[arg-type]
    monkeypatch.setattr(intake_service, "run_intake", fake)
    return fake


async def agree(h: Harness, language: str = "en") -> None:
    label = {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}[language]
    await h.chat.send("/start")
    await h.chat.press(label)
    await h.chat.press(t("agree", language))


async def to_review(h: Harness, monkeypatch: pytest.MonkeyPatch, language: str = "en") -> None:
    """Consent, describe (no follow-ups), pick the first candidate, confirm: a question is shown."""
    fake_intake(monkeypatch, intake_result())
    await agree(h, language)
    await h.chat.send("Why is our ward road still not built?")
    await h.chat.press(UNIVERSITY["name_ta"] if language == "ta" else UNIVERSITY["name"])
    await h.chat.press(t("confirm", language))


async def only_case(h: Harness) -> Case:
    async with h.factory() as session:
        return (await session.execute(select(Case))).scalar_one()


async def test_tamil_happy_path_from_start_to_pdf_and_deadlines(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = fake_intake(monkeypatch, intake_result(follow_ups=FOLLOW_UPS_TA))
    chat, request = h.chat, h.request

    await chat.send("/start")
    assert [label for label, _ in request.buttons()] == ["English", "हिन्दी", "தமிழ்"]
    await chat.press("தமிழ்")
    assert request.last_text() == t("privacy", "ta")
    assert [label for label, _ in request.buttons()] == [t("agree", "ta")]
    assert set((await h.counts()).values()) == {0}, "nothing is stored before agreement"

    await chat.press(t("agree", "ta"))
    async with h.factory() as session:
        user = (await session.execute(select(User))).scalar_one()
    assert (user.channel, user.language) == ("telegram", "ta")
    assert request.last_text() == t("describe", "ta")

    await chat.send(CONCERN_TA)
    assert intake.calls == [(CONCERN_TA, "ta")]
    assert request.last_text() == FOLLOW_UPS_TA[0]
    await chat.send("கணிதம்")
    assert request.last_text() == FOLLOW_UPS_TA[1]
    await chat.send("ஏப்ரல் 2026")
    assert request.last_text() == t("choose_authority", "ta")  # at most two follow-ups
    labels = [label for label, _ in request.buttons()]
    assert labels == [
        UNIVERSITY["name_ta"],
        "Sample Central Board, Regional Office",
        t("other", "ta"),
    ]

    await chat.press(UNIVERSITY["name_ta"])
    assert UNIVERSITY["pio_address"] in request.last_text()
    await chat.press(t("confirm", "ta"))
    case = await only_case(h)
    assert (case.jurisdiction, case.language, case.status) == ("tamil_nadu", "ta", "draft")
    assert (case.authority_name, case.pio_address) == (
        UNIVERSITY["name_ta"],
        UNIVERSITY["pio_address"],
    )
    request_text = h.llm.calls[0]["input"]
    assert CONCERN_TA in request_text and "கணிதம்" in request_text and "ஏப்ரல் 2026" in request_text
    assert request.last_text() == t(
        "rewritten", "ta", text=REWRITE_TA.rewritten, reason=REWRITE_TA.reason
    )
    for key in ("accept", "edit", "add", "done"):
        chat.button(t(key, "ta"))

    await chat.press(t("accept", "ta"))
    assert request.last_text().endswith(t("accepted", "ta"))
    async with h.factory() as session:
        assert (await session.execute(select(Question.accepted))).scalar_one() is True

    await chat.press(t("done", "ta"))
    assert request.last_text() == t("ask_name", "ta")
    await chat.send(NAME)
    assert request.last_text() == t("ask_address", "ta")
    await chat.send(ADDRESS)
    assert request.last_text() == t("ask_bpl", "ta")
    await chat.press(t("no", "ta"))
    rules = load_rules("tamil_nadu")
    fee = rules.local.application_fee.rupees
    assert request.last_text() == t("ask_payment", "ta", fee=fee)
    payment_labels = labels_for("ta").payment_modes
    assert sorted(request.buttons()) == sorted(
        (payment_labels[mode], f"pay:{mode}") for mode in rules.local.payment_modes.modes
    )
    await chat.press(payment_labels["postal_money_order"])
    assert request.last_text() == t("ask_place", "ta")

    await chat.send("சென்னை")
    [document] = h.renderer.documents
    assert (document.language, document.jurisdiction) == ("ta", "tamil_nadu")
    assert (document.applicant_name, document.applicant_address) == (NAME, ADDRESS)
    assert (document.payment_mode, document.place, document.bpl) == (
        "postal_money_order",
        "சென்னை",
        False,
    )
    assert document.questions == COMPOSE_TA.questions and document.prepared_on == TODAY
    [sent_pdf] = request.sent("sendDocument")
    assert sent_pdf.params["caption"] == t("pdf_caption", "ta")
    assert request.documents == [b"%PDF-1.7 fake application 1"]
    checklist = request.texts()[-2]
    assert f"₹{fee}" in checklist and t("check_confirm", "ta") in checklist
    assert t("check_proof", "ta") in checklist
    assert all(payment_labels[mode] in checklist for mode in rules.local.payment_modes.modes)
    assert request.last_text() == t("ask_filed", "ta")
    compose_input = h.llm.calls[1]["input"]
    assert NAME not in compose_input and ADDRESS not in compose_input

    await chat.send("இன்று")
    assert request.last_text() == t("ask_mode", "ta")
    assert {data for _, data in request.buttons()} == {
        "mode:rti_online",
        "mode:post",
        "mode:in_person",
    }
    await chat.press(t("mode_post", "ta"))
    case = await only_case(h)
    assert (case.status, case.filed_on, case.filing_mode) == ("reply_due", TODAY, "post")
    reply = request.last_text()
    # Tamil Nadu: receipt estimated 7 days after posting, 30 days to reply, 30 more to appeal.
    assert "3 டிசம்பர் 2026" in reply and "2 ஜனவரி 2027" in reply
    assert format_date(date(2026, 12, 3), "ta") == "3 டிசம்பர் 2026"
    assert t("estimated", "ta") in reply
    assert "பொதுத் தகவல் அலுவலர்" in reply and "முதல் மேல்முறையீடு" in reply  # glossary terms

    await chat.send("/cases")
    listing = request.last_text()
    assert UNIVERSITY["name_ta"] in listing and t("status_reply_due", "ta") in listing
    assert "3 டிசம்பர் 2026" in listing

    said = request.everything_said()
    assert NAME not in said and ADDRESS not in said, "applicant details are never echoed"


async def test_consent_is_required_before_any_row(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = fake_intake(monkeypatch)
    await h.chat.send("/start")
    await h.chat.press("English")
    await h.chat.send("My problem is that the road is broken")
    assert intake.calls == []
    assert set((await h.counts()).values()) == {0}
    assert h.request.last_text() == t("use_buttons", "en")
    await h.chat.press(t("agree", "en"))
    assert (await h.counts())["users"] == 1


async def test_hindi_start_shows_the_hindi_notice(h: Harness) -> None:
    await h.chat.send("/start")
    await h.chat.press("हिन्दी")
    assert h.request.last_text() == t("privacy", "hi")
    assert "सूचना का अधिकार अधिनियम, 2005" in h.request.last_text()


@pytest.mark.parametrize(
    ("failure", "key", "retry_button"),
    [
        (ModelBusy("busy"), "busy", True),
        (ModelOutputInvalid("invalid"), "rephrase", False),
        (ModelIncomplete("max_output_tokens", "partial"), "incomplete", True),
    ],
    ids=["busy", "invalid", "incomplete"],
)
async def test_model_failures_are_explained_and_recoverable(
    h: Harness,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    key: str,
    retry_button: bool,
) -> None:
    intake = fake_intake(monkeypatch, failure, intake_result())
    await agree(h, "ta")
    await h.chat.send(CONCERN_TA)
    assert h.request.last_text() == t(key, "ta")
    assert (await h.counts())["cases"] == 0
    if retry_button:
        await h.chat.press(t("retry", "ta"))
    else:
        assert t("retry", "ta") not in [label for label, _ in h.request.buttons()]
        await h.chat.send(CONCERN_TA)
    assert h.request.last_text() == t("choose_authority", "ta")
    assert intake.calls == [(CONCERN_TA, "ta"), (CONCERN_TA, "ta")]


async def test_unexpected_error_gets_a_plain_apology(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_intake(monkeypatch, RuntimeError("internal detail 98765"))
    await agree(h, "ta")
    await h.chat.send(CONCERN_TA)
    assert h.request.last_text() == t("error", "ta")
    assert "internal detail" not in h.request.everything_said()


async def test_personal_information_warning_then_a_usable_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = await start_harness(tmp_path, FakeLLM(REFUSED_EN, REWRITE_EN))
    try:
        await to_review(h, monkeypatch)
        warning = h.request.last_text()
        basis = load_rules("tamil_nadu").act.personal_information.basis
        assert warning.startswith(t("personal_info", "en", basis=basis))
        assert REFUSED_EN.suggestion is not None and REFUSED_EN.suggestion in warning
        labels = [label for label, _ in h.request.buttons()]
        assert labels == [t("add", "en"), t("done", "en")], "nothing to accept or edit"

        await h.chat.press(t("done", "en"))  # every question was refused: nothing to export
        assert h.request.last_text() == t(
            "blocked", "en", items="- " + t("flag_no_questions", "en")
        )
        await h.chat.press(t("add", "en"))
        assert h.request.last_text() == t("add_prompt", "en")
        await h.chat.send("Why was the ward road contract given?")
        assert h.request.last_text().startswith(
            t("rewritten", "en", text=REWRITE_EN.rewritten, reason=REWRITE_EN.reason)
        )
        async with h.factory() as session:
            rows = (await session.execute(select(Question).order_by(Question.position))).scalars()
            assert [q.personal_information for q in rows] == [True, False]
    finally:
        await h.close()


async def test_edit_and_add_another_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = await start_harness(tmp_path, FakeLLM(REWRITE_EN, REWRITE_EN))
    try:
        await to_review(h, monkeypatch)
        await h.chat.press(t("edit", "en"))
        assert h.request.last_text() == t("edit_prompt", "en")
        await h.chat.send("Copy of the ward road work order, 2025 to 2026")
        assert h.request.last_text() == t("saved_edit", "en")
        await h.chat.press(t("add", "en"))
        await h.chat.send("Why is the road so narrow?")
        async with h.factory() as session:
            rows = list(
                (await session.execute(select(Question).order_by(Question.position))).scalars()
            )
        assert [(q.position, q.accepted) for q in rows] == [(1, True), (2, False)]
        assert rows[0].rewritten_text == "Copy of the ward road work order, 2025 to 2026"
    finally:
        await h.close()


async def test_other_authority_typed_by_the_user(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_intake(monkeypatch, intake_result(hint="unknown", authorities=[]))
    await agree(h, "en")
    await h.chat.send("The panchayat office will not show me the water tank accounts")
    assert [label for label, _ in h.request.buttons()] == [t("other", "en")]
    await h.chat.press(t("other", "en"))
    assert h.request.last_text() == t("authority_name", "en")
    await h.chat.send("Sample Village Panchayat Office")
    assert h.request.last_text() == t("authority_address", "en")
    await h.chat.send("Panchayat Office, 3 Temple Street, Sampleur 600002")
    assert h.request.last_text() == t("choose_jurisdiction", "en")  # the hint was "unknown"
    await h.chat.press(t("jur_tamil_nadu", "en"))
    assert "3 Temple Street" in h.request.last_text()
    await h.chat.press(t("change", "en"))
    assert h.request.last_text() == t("choose_authority", "en")
    await h.chat.press(t("other", "en"))
    await h.chat.send("Sample Village Panchayat Office")
    await h.chat.send("Panchayat Office, 3 Temple Street, Sampleur 600002")
    await h.chat.press(t("jur_tamil_nadu", "en"))
    await h.chat.press(t("confirm", "en"))
    case = await only_case(h)
    assert (case.jurisdiction, case.authority_name) == (
        "tamil_nadu",
        "Sample Village Panchayat Office",
    )
    assert case.pio_address == "Panchayat Office, 3 Temple Street, Sampleur 600002"


async def test_bpl_applicant_skips_payment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = await start_harness(tmp_path, FakeLLM(REWRITE_EN, COMPOSE_EN))
    try:
        await to_review(h, monkeypatch)
        await h.chat.press(t("done", "en"))
        await h.chat.send(NAME)
        await h.chat.send(ADDRESS)
        await h.chat.press(t("yes", "en"))
        assert h.request.last_text() == t("ask_place", "en")
        await h.chat.send("Chennai")
        [document] = h.renderer.documents
        assert (document.bpl, document.payment_mode) == (True, None)
        assert t("fee_bpl", "en") in h.request.texts()[-2]
        async with h.factory() as session:
            applicant = (await session.execute(select(Applicant))).scalar_one()
        assert (applicant.name, applicant.address, applicant.bpl) == (NAME, ADDRESS, True)
    finally:
        await h.close()


async def test_filing_date_is_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = await start_harness(tmp_path, FakeLLM(REWRITE_EN, COMPOSE_EN))
    try:
        await to_review(h, monkeypatch)
        await h.chat.press(t("done", "en"))
        await h.chat.send(NAME)
        await h.chat.send(ADDRESS)
        await h.chat.press(t("no", "en"))
        await h.chat.tap("pay:not_a_mode")  # a forged button: asked again, nothing stored
        fee = load_rules("tamil_nadu").local.application_fee.rupees
        assert h.request.last_text() == t("ask_payment", "en", fee=fee)
        await h.chat.press(labels_for("en").payment_modes["cash"])
        await h.chat.send("Chennai")
        for bad in ("27/10/2026", "2026-13-01", "tomorrow"):
            await h.chat.send(bad)
            assert h.request.last_text() == t("bad_date", "en")
        await h.chat.send("2026-10-28")
        assert h.request.last_text() == t("future_date", "en")
        await h.chat.send("2026-10-20")
        await h.chat.press(t("mode_in_person", "en"))
        case = await only_case(h)
        assert (case.filed_on, case.filing_mode, case.status) == (
            date(2026, 10, 20),
            "in_person",
            "reply_due",
        )
    finally:
        await h.close()


@pytest.mark.parametrize(
    ("rti_online", "key"),
    [(True, "rti_online_yes"), (False, "rti_online_no"), (None, "rti_online_unknown")],
)
async def test_rti_online_is_shown_without_assuming(
    h: Harness, monkeypatch: pytest.MonkeyPatch, rti_online: bool | None, key: str
) -> None:
    fake_intake(monkeypatch, intake_result(authorities=[{**UNIVERSITY, "rti_online": rti_online}]))
    await agree(h, "en")
    await h.chat.send("Why is our ward road still not built?")
    await h.chat.press(UNIVERSITY["name"])
    assert t(key, "en") in h.request.last_text()
