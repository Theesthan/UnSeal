"""Tamil and Hindi eval (docs/language-eval-plan.md): run the cases, record outputs, score them.

Automated checks per call: A1 schema (first call and after one retry), A2 no invented legal
values, A3 placeholders kept, A4 share of letters in the target script. Reviewers score T and L
in the generated results sheet; the live runner is tests/golden/lang_eval/test_lang_eval_live.py.
"""

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from unseal.harness.steps import LANGUAGE_NAMES as STEP_LANGUAGES
from unseal.harness.steps import StructuredLLM, run_step
from unseal.llm.client import ModelBusy, ModelIncomplete, ModelOutputInvalid
from unseal.llm.glossary import missed_terms, term_errors
from unseal.llm.prompts import load_prompt
from unseal.llm.schemas import STEP_SCHEMAS, StepOutput

# apps/api/src/unseal/evals/lang_eval.py -> apps/api; the eval runs from a source checkout only.
_API_DIR = Path(__file__).resolve().parents[3]
CASES_PATH = _API_DIR / "tests" / "golden" / "lang_eval" / "cases.json"
RECORDED_DIR = _API_DIR / "tests" / "fixtures" / "recorded" / "lang_eval"
RESULTS_DIR = _API_DIR.parents[1] / "docs" / "eval"

LANGUAGE_NAMES = {code: STEP_LANGUAGES[code] for code in ("ta", "hi")}  # what the eval covers
_SCRIPT_BLOCKS = {"ta": (0x0B80, 0x0BFF), "hi": (0x0900, 0x097F)}
ALLOWED_NUMBERS = frozenset({2005})  # the year in the Act's own name may appear
FIRST_CALL_VALID_PER_TEN = 9  # plan: at least 9 of 10 calls valid on the first try

_LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
# Inline list markers: "(1) ..." or "1) ..." after a space. "6(1)" stays (a citation's clause).
_INLINE_ENUM = re.compile(r"(?:(?<=\s)|^)\(?\d{1,2}\)(?=\s)", re.MULTILINE)
# "1ஆம் ஆண்டு", "12वीं", "2nd": ordinals are never legal values. A bare day ("5 September")
# still counts. ponytail: an ordinal day of the month ("by the 5th") slips through; the year or
# ISO date around it is still checked.
_ORDINAL = re.compile(r"\d+(?=ஆம்|ஆவது|வது|वीं|वां|वें|वाँ|(?:st|nd|rd|th)\b)")
_NUMBER = re.compile(r"\d+")  # str patterns match Tamil and Devanagari digits too
_PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9_]*>")
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
# A section word counts only when a number follows: "section numbers" is prose, and பிரிவு and
# धारा are also everyday words ("division", "stream"). Currency marks count on their own.
_LEGAL_MARKER = re.compile(
    r"(?:\bsections?|\bsec\.|\bs\.|பிரிவு|धारा)(?=\s*\d)"
    r"|\brs\b\.?|\brupees?\b|₹|ரூபாய்|ரூ\.|रुपये|रुपए|रु\.",
    re.IGNORECASE,
)

CaseId = str


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: CaseId = Field(pattern=r"^(TA|HI)-\d+$")  # also a file name: keep it path-safe
    language: Literal["ta", "hi"]
    kind: Literal["rewrite", "intake", "compose", "appeal_facts"]
    input: str
    expected: str


@dataclass(frozen=True)
class Run:
    output: dict[str, Any] | None
    error: str | None  # "busy", "invalid" or "incomplete"
    schema_retries: int
    request_id: str | None


@dataclass(frozen=True)
class Recording:
    case_id: CaseId
    prompt_version: int
    model: str
    runs: tuple[Run, ...]


@dataclass(frozen=True)
class RunScore:
    error: str | None
    valid: bool
    valid_first: bool
    invented: tuple[str, ...]
    placeholders_kept: bool | None
    script_share: float | None
    term_errors: tuple[str, ...] = ()  # glossary: known-wrong variants used
    missed_terms: tuple[str, ...] = ()  # glossary: named concepts without the preferred term


@dataclass(frozen=True)
class Summary:
    language: str
    calls: int  # busy calls excluded: they say nothing about the model
    busy: int
    first_call_valid: int
    valid: int
    gates: tuple[tuple[str, bool], ...]


def load_cases(path: Path = CASES_PATH) -> list[Case]:
    return TypeAdapter(list[Case]).validate_json(path.read_bytes())


# ---------------------------------------------------------------- automated checks


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _markers(text: str) -> list[str]:
    return [m.group().strip().lower() for m in _LEGAL_MARKER.finditer(text)]


def _numbers(text: str) -> list[int]:
    return [int(m.group()) for m in _NUMBER.finditer(text)]


def invented_legal_values(output: str, source: str) -> list[str]:
    """A2: legal markers and numbers in `output` that `source` does not contain."""
    output = _ORDINAL.sub(" ", _INLINE_ENUM.sub(" ", _LIST_NUMBER.sub("", output)))
    known_markers = set(_markers(source))
    known_numbers = set(_numbers(source)) | ALLOWED_NUMBERS
    markers = [m for m in _unique(_markers(output)) if m not in known_markers]
    numbers = [str(n) for n in dict.fromkeys(_numbers(output)) if n not in known_numbers]
    return markers + numbers


def placeholders_kept(output: str, source: str) -> bool | None:
    """A3: every <PLACEHOLDER> in `source` survives verbatim; None when there are none."""
    wanted = set(_PLACEHOLDER.findall(source))
    return wanted <= set(_PLACEHOLDER.findall(output)) if wanted else None


def script_share(text: str, language: str) -> float | None:
    """A4: share of letters in the target script, ignoring placeholders and acronyms."""
    low, high = _SCRIPT_BLOCKS[language]
    cleaned = _ACRONYM.sub(" ", _PLACEHOLDER.sub(" ", text))
    letters = [ch for ch in cleaned if unicodedata.category(ch)[0] in "LM"]
    if not letters:
        return None
    return sum(low <= ord(ch) <= high for ch in letters) / len(letters)


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


# ---------------------------------------------------------------- running


async def run_case(llm: StructuredLLM, case: Case, runs: int, model: str) -> Recording:
    version = load_prompt(case.kind).version
    attempts = [await _attempt(llm, case) for _ in range(runs)]
    return Recording(case.id, version, model, tuple(attempts))


async def _attempt(llm: StructuredLLM, case: Case) -> Run:
    try:  # the exact request the app sends (harness.steps)
        result = await run_step(llm, case.kind, language=case.language, input=case.input)
    except ModelBusy as exc:
        return Run(None, "busy", 0, exc.request_id)
    except ModelOutputInvalid as exc:
        return Run(None, "invalid", 1, exc.request_id)
    except ModelIncomplete as exc:
        return Run(None, "incomplete", 0, exc.request_id)
    return Run(result.value.model_dump(mode="json"), None, result.schema_retries, result.request_id)


# ---------------------------------------------------------------- scoring


def score(case: Case, recording: Recording) -> list[RunScore]:
    schema = STEP_SCHEMAS[case.kind]
    return [_score_run(case, schema, run) for run in recording.runs]


def _score_run(case: Case, schema: type[StepOutput], run: Run) -> RunScore:
    if run.output is None:
        return RunScore(run.error, False, False, (), None, None)
    try:  # stored runs are re-checked, so a newer value rule applies to old outputs too
        shown = schema.model_validate(run.output).user_text()
    except ValidationError:
        return RunScore("invalid", False, False, (), None, None)
    everything = "\n".join(_strings(run.output))
    # Intake only asks questions, so it is not expected to name the records.
    missed = (
        ()
        if case.kind == "intake"
        else tuple(missed_terms(shown, case.language, f"{case.input}\n{case.expected}"))
    )
    return RunScore(
        error=None,
        valid=True,
        valid_first=run.schema_retries == 0,
        invented=tuple(invented_legal_values(everything, case.input)),
        placeholders_kept=placeholders_kept(everything, case.input),
        script_share=script_share(shown, case.language),
        term_errors=tuple(term_errors(everything, case.language)),
        missed_terms=missed,
    )


def summarize(language: str, cases: list[Case], recordings: list[Recording]) -> Summary:
    by_id = {c.id: c for c in cases}
    scores = [s for rec in recordings for s in score(by_id[rec.case_id], rec)]
    counted = [s for s in scores if s.error != "busy"]
    calls, first = len(counted), sum(s.valid_first for s in counted)
    valid = sum(s.valid for s in counted)
    gates = (
        (
            "A1 schema",
            calls > 0 and first * 10 >= calls * FIRST_CALL_VALID_PER_TEN and valid == calls,
        ),
        ("A2 no invented legal values", not any(s.invented for s in counted)),
        ("A3 placeholders kept", all(s.placeholders_kept is not False for s in counted)),
        ("Run complete (no busy calls)", len(scores) == len(counted)),
    )
    return Summary(language, calls, len(scores) - calls, first, valid, gates)


# ---------------------------------------------------------------- results sheet


def render_results(language: str, cases: list[Case], recordings: list[Recording]) -> str:
    by_case = {rec.case_id: rec for rec in recordings}
    mine = [c for c in cases if c.language == language and c.id in by_case]
    summary = summarize(language, mine, [by_case[c.id] for c in mine])
    name = LANGUAGE_NAMES[language]
    lines = [
        f"# {name} eval results",
        "",
        "Generated by the live eval (`uv run pytest -m live tests/golden/lang_eval`). Automated",
        "columns are overwritten on every run; copy reviewer scores elsewhere before rerunning.",
        "",
        *_meta_lines(mine, by_case),
        "",
        "## Automated gates",
        "",
        "| Gate | Result |",
        "| --- | --- |",
        *(f"| {gate} | {'PASS' if passed else 'FAIL'} |" for gate, passed in summary.gates),
        "",
        f"First-call valid: {summary.first_call_valid} of {summary.calls} calls; valid after one "
        f"retry: {summary.valid} of {summary.calls}; busy (excluded): {summary.busy}.",
        "",
        "## Cases",
        "",
        f"Script = lowest share of letters in {name} script across valid runs (A4, target 80%).",
        "Reviewers fill T (pass or fail against Expected) and L1 to L3 (0 to 2 each).",
        "",
        "Term errors = known-wrong glossary variants used. Missed terms = concepts the case names",
        "whose preferred glossary term is absent (not counted for intake).",
        "",
        "| Case | Kind | First-call valid | Invented | Placeholders | Script | Term errors "
        "| Missed terms | T | L1 | L2 | L3 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *(_case_row(c, score(c, by_case[c.id])) for c in mine),
        "",
        "## Outputs",
        "",
    ]
    for c in mine:
        lines.extend(_case_outputs(c, by_case[c.id]))
    return "\n".join(lines) + "\n"


def _meta_lines(cases: list[Case], by_case: dict[CaseId, Recording]) -> list[str]:
    if not cases:
        return ["No recorded runs."]
    first = by_case[cases[0].id]
    versions = {c.kind: by_case[c.id].prompt_version for c in cases}
    prompts = ", ".join(f"{kind} v{version}" for kind, version in sorted(versions.items()))
    return [f"Model: `{first.model}`. Runs per case: {len(first.runs)}. Prompts: {prompts}."]


def _case_row(case: Case, scores: list[RunScore]) -> str:
    valid = [s for s in scores if s.valid]
    invented = ", ".join(_unique(v for s in scores for v in s.invented)) or "none"
    kept = [s.placeholders_kept for s in valid if s.placeholders_kept is not None]
    placeholders = "n/a" if not kept else ("kept" if all(kept) else "LOST")
    shares = [s.script_share for s in valid if s.script_share is not None]
    script = f"{min(shares):.0%}" if shares else "n/a"
    first = f"{sum(s.valid_first for s in scores)}/{len(scores)}"
    errors = ", ".join(_unique(t for s in valid for t in s.term_errors)) or "none"
    missed = (
        "n/a"
        if case.kind == "intake"
        else ", ".join(_unique(t for s in valid for t in s.missed_terms)) or "none"
    )
    automated = f"| {case.id} | {case.kind} | {first} | {invented} | {placeholders} | {script} |"
    return f"{automated} {errors} | {missed} |  |  |  |  |"  # T, L1 to L3: for the reviewer


def _case_outputs(case: Case, recording: Recording) -> list[str]:
    lines = [
        f"### {case.id} ({case.kind})",
        "",
        f"**Input:** {case.input}",
        "",
        f"**Expected:** {case.expected}",
        "",
    ]
    for number, run in enumerate(recording.runs, start=1):
        if run.output is None:
            lines.extend([f"Run {number}: error ({run.error}).", ""])
            continue
        shown = json.dumps(run.output, ensure_ascii=False, indent=2)
        lines.extend([f"Run {number}:", "", "```json", shown, "```", ""])
    return lines


# ---------------------------------------------------------------- recordings


def save_recording(recording: Recording, folder: Path) -> Path:
    if not re.fullmatch(r"(TA|HI)-\d+", recording.case_id):
        raise ValueError(f"unexpected case id {recording.case_id!r}")
    folder = folder / f"v{recording.prompt_version}"  # one folder per prompt version
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{recording.case_id}.json"
    path.write_text(json.dumps(asdict(recording), ensure_ascii=False, indent=2) + "\n", "utf-8")
    return path


def load_recording(path: Path) -> Recording:
    data = json.loads(path.read_text("utf-8"))
    runs = tuple(Run(**run) for run in data["runs"])
    return Recording(data["case_id"], data["prompt_version"], data["model"], runs)


def write_results(
    language: str, cases: list[Case], recordings: list[Recording], folder: Path = RESULTS_DIR
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    sheet = folder / f"language-eval-results-{language}.md"
    sheet.write_text(render_results(language, cases, recordings), "utf-8")
    return sheet


def rescore(recorded: Path = RECORDED_DIR, results: Path = RESULTS_DIR) -> list[Summary]:
    """Re-check saved runs and rewrite the sheets: no API calls, so a checker fix costs nothing."""
    cases = load_cases()
    every = load_recordings(recorded)
    if every:
        write_comparison(every, results)
    recordings = _latest(every)
    summaries = []
    for language in LANGUAGE_NAMES:
        mine = [c for c in cases if c.language == language]
        ids = {c.id for c in mine}
        theirs = [r for r in recordings if r.case_id in ids]
        if theirs:
            write_results(language, mine, theirs, results)
            summaries.append(summarize(language, mine, theirs))
    return summaries


def load_recordings(folder: Path = RECORDED_DIR) -> list[Recording]:
    """Every saved recording, all prompt versions."""
    return [load_recording(path) for path in sorted(folder.glob("v*/*.json"))]


def _latest(recordings: list[Recording]) -> list[Recording]:
    best: dict[CaseId, Recording] = {}
    for rec in recordings:
        if rec.case_id not in best or rec.prompt_version > best[rec.case_id].prompt_version:
            best[rec.case_id] = rec
    return list(best.values())


# ---------------------------------------------------------------- prompt version comparison


def compare_versions(recordings: list[Recording]) -> str:
    """Validity, term errors and missed terms per language and prompt version."""
    by_id = {c.id: c for c in load_cases()}
    scores = {(r.case_id, r.prompt_version): score(by_id[r.case_id], r) for r in recordings}
    versions = sorted({version for _, version in scores})
    lines = [
        "# Prompt versions compared",
        "",
        "Generated by `rescore()` from the recordings. Term errors and missed terms use",
        "`src/unseal/llm/glossary.json`; lower is better. Calls exclude busy ones.",
        "",
        "| Language | Prompt | Calls | First-call valid | Term errors | Missed terms | Invented |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for language, name in LANGUAGE_NAMES.items():
        for version in versions:
            mine = [
                s
                for (case_id, v), runs in scores.items()
                if v == version and by_id[case_id].language == language
                for s in runs
                if s.error != "busy"
            ]
            if mine:
                lines.append(_version_row(name, version, mine))
    header = [f"Term errors v{v}" for v in versions] + [f"Missed v{v}" for v in versions]
    lines += [
        "",
        "## Per case",
        "",
        "| Case | Kind | " + " | ".join(header) + " |",
        "| --- | --- |" + " --- |" * len(header),
    ]
    for case_id in sorted({case_id for case_id, _ in scores}, key=_case_order):
        cells = [_total(scores.get((case_id, v)), "term_errors") for v in versions]
        cells += [_total(scores.get((case_id, v)), "missed_terms") for v in versions]
        lines.append(f"| {case_id} | {by_id[case_id].kind} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _version_row(name: str, version: int, runs: list[RunScore]) -> str:
    valid = [s for s in runs if s.valid]
    return (
        f"| {name} | v{version} | {len(runs)} | {sum(s.valid_first for s in runs)} | "
        f"{sum(len(s.term_errors) for s in valid)} | {sum(len(s.missed_terms) for s in valid)} | "
        f"{sum(bool(s.invented) for s in valid)} |"
    )


def _total(runs: list[RunScore] | None, field: str) -> str:
    if runs is None:
        return "n/a"
    return str(sum(len(getattr(s, field)) for s in runs if s.valid))


def _case_order(case_id: CaseId) -> tuple[str, int]:
    prefix, number = case_id.split("-")
    return (prefix, int(number))


def write_comparison(recordings: list[Recording], folder: Path = RESULTS_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "prompt-versions.md"
    path.write_text(compare_versions(recordings), "utf-8")
    return path


def select_cases(cases: list[Case], language: str, only: str) -> list[Case]:
    """Cases for `language`, narrowed to the comma-separated ids in `only` when given."""
    mine = [c for c in cases if c.language == language]
    wanted = {part.strip() for part in only.split(",") if part.strip()}
    if not wanted:
        return mine
    unknown = wanted - {c.id for c in cases}
    if unknown:
        raise ValueError(f"unknown case ids: {sorted(unknown)}")
    return [c for c in mine if c.id in wanted]
