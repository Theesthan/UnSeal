"""Live Tamil and Hindi eval (docs/language-eval-plan.md). Opt-in; spends real tokens.

From apps/api:

    uv run pytest -m live tests/golden/lang_eval              # both languages, 3 runs per case
    uv run pytest -m live tests/golden/lang_eval -k tamil     # one language
    LANG_EVAL_RUNS=1 uv run pytest -m live tests/golden/lang_eval   # quick pass
    LANG_EVAL_CASES=TA-8,TA-9 uv run pytest -m live tests/golden/lang_eval -k tamil  # rerun some

Records every run to tests/fixtures/recorded/lang_eval/v<prompt>/<case>.json (fictional), then
re-scores every recording (so a partial rerun keeps the full picture), rewrites
docs/eval/language-eval-results-<lang>.md and prompt-versions.md, and fails if an automated gate
fails. A pass here is necessary, not sufficient: T and L are scored by people.
"""

import os

import pytest
from pydantic import ValidationError

from unseal.config import Settings
from unseal.evals.lang_eval import (
    RECORDED_DIR,
    RESULTS_DIR,
    load_cases,
    rescore,
    run_case,
    save_recording,
    select_cases,
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
    cases = select_cases(load_cases(), language, os.environ.get("LANG_EVAL_CASES", ""))
    if not cases:
        pytest.skip(f"LANG_EVAL_CASES selects no {language} case")
    llm = build_client(settings)

    for case in cases:  # sequential on purpose: parallel calls invite 503s on a shared GPU pool
        save_recording(await run_case(llm, case, runs, settings.bharatcode_model), RECORDED_DIR)

    summary = next(s for s in rescore() if s.language == language)
    failed = [gate for gate, passed in summary.gates if not passed]
    sheet = RESULTS_DIR / f"language-eval-results-{language}.md"
    assert not failed, f"automated gates failed: {failed}; see {sheet}"
