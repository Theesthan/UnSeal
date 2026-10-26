"""Tamil and Hindi eval: case file, automated checks (A2 to A4), runner, gates and results sheet.
Runs offline with a scripted model; the live run is
tests/golden/lang_eval/test_lang_eval_live.py."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel

from unseal.config import Settings
from unseal.evals.lang_eval import (
    CASES_PATH,
    MAX_OUTPUT_TOKENS,
    Case,
    Recording,
    Run,
    invented_legal_values,
    load_cases,
    load_recording,
    placeholders_kept,
    render_results,
    run_case,
    save_recording,
    score,
    script_share,
    summarize,
)
from unseal.llm.client import (
    ModelBusy,
    ModelIncomplete,
    ModelOutputInvalid,
    StructuredResult,
    build_client,
)
from unseal.llm.schemas import AppealFacts, Compose, Intake, Rewrite

pytestmark = pytest.mark.anyio

TAMIL_SUBJECT = "விடைத்தாள் நகல் கோரும் விண்ணப்பம் <REG_NO>"
COMPOSE_TA = Compose(subject=TAMIL_SUBJECT, questions=["மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் நகல்"])


# ---------------------------------------------------------------- case file


def test_case_file_has_ten_cases_per_language_in_the_planned_mix() -> None:
    cases = load_cases()
    assert len({c.id for c in cases}) == len(cases) == 20
    for language, prefix in (("ta", "TA-"), ("hi", "HI-")):
        mine = [c for c in cases if c.language == language]
        assert all(c.id.startswith(prefix) for c in mine)
        assert Counter(c.kind for c in mine) == {
            "rewrite": 4,
            "intake": 3,
            "compose": 2,
            "appeal_facts": 1,
        }
    with_placeholders = {c.id for c in cases if "<" in c.input}
    assert with_placeholders == {"TA-8", "TA-9", "HI-8", "HI-9"}
    assert CASES_PATH.name == "cases.json"


# ---------------------------------------------------------------- A2: invented legal values


@pytest.mark.parametrize(
    ("output", "source", "invented"),
    [
        ("धारा 6(1) के अंतर्गत", "", ["धारा", "6", "1"]),
        ("30 दिनों के भीतर", "", ["30"]),
        ("Section 7 applies", "", ["section", "7"]),
        ("₹10 शुल्क", "", ["₹", "10"]),
        ("௩௦ நாட்களுக்குள்", "", ["30"]),  # Tamil digits are numbers too
        ("3 ஆகஸ்ட் 2026 அன்று", "Filed 2026-08-03", []),  # same date, different format
        ("தகவல் அறியும் உரிமைச் சட்டம், 2005", "", []),  # the Act's year is allowed
        ("1. पहला\n2. दूसरा", "", []),  # list numbering is not a legal value
        ("12वीं की परीक्षा", "12वीं कक्षा", []),
        ("Do not add section numbers", "", []),  # the word alone is not a citation
        ("கணக்குப் பிரிவு அலுவலர்", "", []),  # பிரிவு also means "division"
        ("பிரிவு 8 இன் கீழ்", "", ["பிரிவு", "8"]),
    ],
)
def test_invented_legal_values(output: str, source: str, invented: list[str]) -> None:
    assert invented_legal_values(output, source) == invented


# ---------------------------------------------------------------- A3 and A4


def test_placeholders_kept() -> None:
    assert placeholders_kept("நகல் <REG_NO>", "copy for <REG_NO>") is True
    assert placeholders_kept("நகல் REG_NO", "copy for <REG_NO>") is False
    assert placeholders_kept("anything", "no placeholders here") is None


def test_script_share_ignores_placeholders_and_acronyms() -> None:
    assert script_share("CBSE விடைத்தாள் <REG_NO>", "ta") == 1.0
    assert script_share("answer sheet", "ta") == 0.0
    assert script_share("उत्तर पुस्तिका", "ta") == 0.0
    assert script_share("उत्तर पुस्तिका EPFO", "hi") == 1.0
    assert script_share("<REG_NO> CBSE", "hi") is None  # nothing left to judge


# ---------------------------------------------------------------- runner


class ScriptedLLM:
    """Stands in for LLMClient.structured_call: replays results, records every call."""

    def __init__(self, *results: BaseModel | Exception | tuple[BaseModel, int]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        value, retries = item if isinstance(item, tuple) else (item, 0)
        return StructuredResult(
            value=value, request_id="req-x", schema_retries=retries, budget_raised=False
        )


def case(case_id: str = "TA-8", kind: str = "compose", text: str = "copy for <REG_NO>") -> Case:
    language = "ta" if case_id.startswith("TA") else "hi"
    return Case(id=case_id, language=language, kind=kind, input=text, expected="x")


async def test_run_case_uses_the_step_prompt_schema_and_language() -> None:
    llm = ScriptedLLM(COMPOSE_TA, (COMPOSE_TA, 1), ModelOutputInvalid("bad", "req-bad"))
    recording = await run_case(llm, case(), runs=3, model="qwen-3.8-27b")

    assert [r.schema_retries for r in recording.runs] == [0, 1, 1]
    assert [r.error for r in recording.runs] == [None, None, "invalid"]
    assert recording.runs[0].output == COMPOSE_TA.model_dump()
    assert recording.prompt_version >= 1
    first = llm.calls[0]
    assert first["output"] is Compose
    assert first["input"] == "copy for <REG_NO>"
    assert "Tamil" in first["instructions"]
    assert first["reasoning_effort"] is None


async def test_intake_runs_without_reasoning_and_busy_is_recorded() -> None:
    intake = Intake(
        jurisdiction_hint="tamil_nadu",
        authority=None,
        time_period=None,
        records_wanted=[],
        delivery_mode="unknown",
        bpl="unknown",
        follow_up_questions=["எந்த அலுவலகம்?"],
        ready_to_draft=False,
    )
    llm = ScriptedLLM(intake, ModelBusy("busy"))
    recording = await run_case(llm, case("TA-7", "intake", "கோப்பு"), runs=2, model="m")
    assert llm.calls[0]["reasoning_effort"] == "none"
    assert [r.error for r in recording.runs] == [None, "busy"]


# ---------------------------------------------------------------- scoring, gates, sheet


def recording_for(c: Case, *runs: Run) -> Recording:
    return Recording(case_id=c.id, prompt_version=1, model="m", runs=runs)


def ok(value: BaseModel, retries: int = 0) -> Run:
    return Run(output=value.model_dump(), error=None, schema_retries=retries, request_id="r")


def test_score_checks_each_valid_run() -> None:
    c = case()
    leaky = Compose(subject="பிரிவு 6 கீழ் விண்ணப்பம்", questions=["answer script copy"])
    scores = score(c, recording_for(c, ok(COMPOSE_TA), ok(leaky, 1), Run(None, "invalid", 1, "r")))

    assert [s.valid_first for s in scores] == [True, False, False]
    assert [s.valid for s in scores] == [True, True, False]
    assert scores[0].invented == () and scores[0].placeholders_kept is True
    assert scores[1].invented == ("பிரிவு", "6") and scores[1].placeholders_kept is False
    assert scores[0].script_share == 1.0 and scores[1].script_share is not None
    assert scores[2].invented == () and scores[2].placeholders_kept is None


def ten_cases(language: str = "ta") -> list[Case]:
    prefix = "TA" if language == "ta" else "HI"
    return [case(f"{prefix}-{i}", "compose", "copy for <REG_NO>") for i in range(1, 11)]


def test_gates_pass_at_nine_of_ten_first_call() -> None:
    cases = ten_cases()
    recordings = [recording_for(c, ok(COMPOSE_TA, 1 if i == 0 else 0)) for i, c in enumerate(cases)]
    summary = summarize("ta", cases, recordings)
    assert summary.first_call_valid == 9 and summary.calls == 10
    assert all(passed for _, passed in summary.gates)


def test_gates_fail_on_invalid_invented_lost_placeholder_or_busy() -> None:
    cases = ten_cases()
    bad = Compose(subject="₹10 கட்டணம்", questions=["நகல்"])  # invents a fee, drops <REG_NO>
    runs = [ok(COMPOSE_TA)] * 7 + [
        Run(None, "invalid", 1, "r"),
        ok(bad),
        Run(None, "busy", 0, None),
    ]
    summary = summarize(
        "ta", cases, [recording_for(c, r) for c, r in zip(cases, runs, strict=True)]
    )
    gates = dict(summary.gates)
    assert summary.busy == 1 and summary.calls == 9
    assert gates == {
        "A1 schema": False,
        "A2 no invented legal values": False,
        "A3 placeholders kept": False,
        "Run complete (no busy calls)": False,
    }


def test_results_sheet_is_ready_for_reviewers() -> None:
    cases = ten_cases()
    recordings = [recording_for(c, ok(COMPOSE_TA)) for c in cases]
    sheet = render_results("ta", cases, recordings)
    assert "# Tamil eval results" in sheet
    assert "| TA-1 | compose |" in sheet
    assert "A1 schema | PASS" in sheet
    assert "| T | L1 | L2 | L3 |" in sheet  # blank columns for the native-speaker review
    assert TAMIL_SUBJECT in sheet  # outputs are shown so reviewers can score them
    assert chr(0x2014) not in sheet  # no em dashes in generated docs (user rule)


def test_recordings_round_trip(tmp_path: Path) -> None:
    c = case()
    recording = recording_for(c, ok(COMPOSE_TA, 1), Run(None, "busy", 0, None))
    path = save_recording(recording, tmp_path)
    assert path == tmp_path / "TA-8.json"
    assert load_recording(path) == recording


def test_recorded_fixtures_still_match_the_schemas() -> None:
    folder = Path(__file__).parents[1] / "fixtures" / "recorded" / "lang_eval"
    files = sorted(folder.glob("*.json")) if folder.exists() else []
    if not files:
        pytest.skip("no recorded lang_eval fixtures yet (run the live eval)")
    by_id = {c.id: c for c in load_cases()}
    for path in files:
        recording = load_recording(path)
        schema = {"rewrite": Rewrite, "intake": Intake, "compose": Compose}.get(
            by_id[recording.case_id].kind, AppealFacts
        )
        for run in recording.runs:
            if run.output is not None:
                schema.model_validate(run.output)


async def test_truncated_output_is_recorded_as_incomplete() -> None:
    llm = ScriptedLLM(ModelIncomplete("max_output_tokens", '{"subj', "req-cut"))
    recording = await run_case(llm, case(), runs=1, model="m")
    assert recording.runs == (Run(None, "incomplete", 0, "req-cut"),)


def test_results_sheet_shows_failed_runs_and_empty_languages() -> None:
    cases = ten_cases()
    recordings = [recording_for(cases[0], Run(None, "invalid", 1, "r"))]
    sheet = render_results("ta", cases, recordings)
    assert "Run 1: error (invalid)." in sheet
    assert "| TA-1 | compose | 0/1 |" in sheet
    assert "No recorded runs." in render_results("hi", cases, recordings)


def test_recording_ids_must_be_path_safe(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_recording(Recording("../TA-1", 1, "m", ()), tmp_path)


async def test_runner_drives_the_real_client_end_to_end(tmp_path: Path) -> None:
    """The scripted fake skips the client; this runs the real LLMClient and openai SDK."""
    sent: list[dict[str, Any]] = []

    def bharatcode(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        message = {
            "type": "message",
            "id": "msg_1",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": COMPOSE_TA.model_dump_json()}],
        }
        body = {"id": "resp_1", "object": "response", "status": "completed", "output": [message]}
        return httpx2.Response(200, json=body, headers={"x-request-id": "req-live"})

    settings = Settings(_env_file=None, bharatcode_api_key="test-key")
    transport = httpx2.AsyncClient(transport=httpx2.MockTransport(bharatcode))
    llm = build_client(settings, http_client=transport)
    recording = await run_case(llm, case(), runs=1, model=settings.bharatcode_model)

    request = sent[0]
    assert request["text"]["format"]["name"] == "Compose"
    assert request["store"] is False
    assert "Tamil" in request["instructions"]
    assert request["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert recording.runs == (Run(COMPOSE_TA.model_dump(mode="json"), None, 0, "req-live"),)
    assert load_recording(save_recording(recording, tmp_path)) == recording


def test_a1_fails_at_eight_of_ten_first_call_even_if_all_recover() -> None:
    cases = ten_cases()
    recordings = [recording_for(c, ok(COMPOSE_TA, 1 if i < 2 else 0)) for i, c in enumerate(cases)]
    summary = summarize("ta", cases, recordings)
    assert (summary.first_call_valid, summary.valid, summary.calls) == (8, 10, 10)
    assert dict(summary.gates)["A1 schema"] is False
