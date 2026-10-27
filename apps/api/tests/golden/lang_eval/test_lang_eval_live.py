"""Live Tamil and Hindi eval (docs/language-eval-plan.md). Opt-in; spends real tokens.

From apps/api:

    uv run pytest -m live tests/golden/lang_eval              # both languages, 3 runs per case
    uv run pytest -m live tests/golden/lang_eval -k tamil     # one language
    LANG_EVAL_RUNS=1 uv run pytest -m live tests/golden/lang_eval   # quick pass

Records every run to tests/fixtures/recorded/lang_eval/v<prompt>/<case>.json (fictional only), writes
docs/eval/language-eval-results-<lang>.md for the native-speaker review, then fails if an automated
gate fails. A pass here is necessary, not sufficient: T and L are scored by people.
"""

import os

import pytest
from pydantic import ValidationError

from unseal.config import Settings
from unseal.evals.lang_eval import (
    RECORDED_DIR,
    load_cases,
    run_case,
    save_recording,
    summarize,
    write_results,
)
from unseal.llm.client import build_client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


@pytest.mark.parametrize(
    "language", [pytest.param("ta", id="tamil"), pytest.param("hi", id="hindi")]
)
async def test_lang_eval(language: str) -> None:
    try:
        settings = Settings()
    except ValidationError:
        pytest.skip("BHARATCODE_API_KEY is not set")
    runs = int(os.environ.get("LANG_EVAL_RUNS", "3"))
    llm = build_client(settings)
    cases = [c for c in load_cases() if c.language == language]

    recordings = []
    for case in cases:  # sequential on purpose: parallel calls invite 503s on a shared GPU pool
        recording = await run_case(llm, case, runs, settings.bharatcode_model)
        save_recording(recording, RECORDED_DIR)
        recordings.append(recording)

    sheet = write_results(language, cases, recordings)
    failed = [gate for gate, passed in summarize(language, cases, recordings).gates if not passed]
    assert not failed, f"automated gates failed: {failed}; see {sheet}"
