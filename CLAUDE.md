# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## UnSeal

UnSeal turns a citizen's concern into a filing-ready RTI application (English, Hindi or Tamil), tracks every statutory deadline, and drafts the first and second appeals. It is a BharatCode Build League entry: submissions close **10 Nov 2026, 11:59 PM IST**; target MVP submission **3 Nov**.
Product spec: [docs/PRD.md](docs/PRD.md). When scope changes, update the PRD first, then this file, and keep the two in sync.
Living state (what exists, what is in flight, open questions): [context.md](context.md).

**Status (26 Oct 2026):** only `apps/api` exists, with the rules data and loader (`rules/engine.py`), settings (`config.py`), the BharatCode client (`llm/client.py`), draft step schemas and prompts (v1), and the Tamil and Hindi eval. Everything else in the layout below is the target; create each piece as it is built, and correct this file if the real structure differs.

## Golden rules (read before every task)

1. **The model writes words; code decides dates, fees and legal grounds.** Never let an LLM compute a deadline, a fee or a section number. Those come only from `rules/engine.py` and `rules/data/*.json`.
2. **Never expose secrets.** Never print, echo, log, commit or paste the values of `.env` or environment variables (in code, tests, commits, PRs, issues or chat). Refer to them by name only. `.env` is git-ignored; only `.env.example` with empty values is committed.
3. **No real personal data anywhere outside the encrypted DB**: not in logs, URLs, analytics, fixtures, prompts, screenshots or commits. Fixtures and demos use fictional applicants only.
4. **Validate every model output** against its Pydantic schema before use. On failure, retry once, then fall back to asking the user.
5. **`BharatCode.txt` stays in the repo root.** It is a hackathon requirement; never delete or move it.
6. Make small, reviewable changes. Run the relevant tests and linters before saying a task is done.

## Repo layout

```
BharatCode.txt            # required by the Build League
CLAUDE.md  README.md  .env.example  docker-compose.yml
apps/
  api/                    # Python 3.12: FastAPI + AI harness + Telegram bot + PDFs
    pyproject.toml  Dockerfile  alembic/
    fonts/                # Noto Sans, Noto Sans Tamil, Noto Sans Devanagari (OFL)
    src/unseal/
      main.py             # FastAPI app and routes (no business logic here)
      config.py           # pydantic-settings; reads env vars
      llm/client.py       # the ONLY place that calls BharatCode
      llm/schemas.py      # Pydantic models for every model output (USER_FACING fields per model)
      llm/prompts.py      # loads prompts/<step>.md (front matter `version: N`)
      llm/glossary.json   # fixed Tamil and Hindi RTI terms (+ known-wrong variants), rendered into prompts
      prompts/            # one versioned prompt file per harness step (inside the package so it ships)
      evals/lang_eval.py  # Tamil and Hindi eval: checks A2 to A4, gates, results sheet
      harness/            # intake, classify, rewrite, validate, compose, read_reply, appeal
      rules/engine.py     # pure functions: deadlines, fees
      rules/data/         # rti_act.json (statute, every jurisdiction) + central.json, tamil_nadu.json
                          #   each rule: basis, source_url (.gov.in/.nic.in), checked_on, quote (ADR 0001)
      pdf/                # WeasyPrint renderer + templates/*.html.j2
      bot/                # python-telegram-bot handlers
      scheduler.py        # APScheduler 3.x reminder job (every 15 min)
      db/                 # SQLAlchemy 2 models, session, crypto.py (Fernet field encryption)
      privacy/redact.py   # log redaction filters
    tests/
      unit/               # rules engine, validators, redaction, crypto
      golden/             # 30 fictional cases + expected flags and rewrites
      golden/lang_eval/   # cases.json (20 Tamil and Hindi cases) + the live eval runner
      fixtures/recorded/  # recorded model responses for offline tests (lang_eval/<case>.json)
  web/                    # Next.js App Router + TypeScript (strict) + Tailwind
docs/
```

## Commands

API (run from `apps/api`; uses `uv`, or `pip install -e ".[dev]"` as a fallback):

| Task | Command |
| --- | --- |
| Install | `uv sync` |
| Run API | `uv run uvicorn unseal.main:app --reload --port 8000` |
| Run bot locally (polling) | `uv run python -m unseal.bot --polling` |
| Tests (offline, default) | `uv run pytest -q` |
| One test | `uv run pytest tests/unit/test_rules_data.py::test_name -q` (or `-k <expr>`) |
| Coverage | `uv run pytest --cov=unseal --cov-report=term-missing` |
| Live smoke call (real API, needs key in `.env`) | `uv run pytest -m live tests/live` |
| Live Tamil and Hindi eval | `uv run pytest -m live tests/golden/lang_eval` (`-k tamil`, `LANG_EVAL_RUNS=1`) |
| Live golden eval (real API) | `uv run pytest -m live tests/golden` |
| Lint and format | `uv run ruff check . --fix && uv run ruff format .` |
| Types | `uv run mypy src` |
| Migrate | `uv run alembic upgrade head` |
| New migration | `uv run alembic revision --autogenerate -m "<what changed>"` |

Web (run from `apps/web`): `npm install`, `npm run dev` (port 3000), `npm run lint`, `npm run build`.
Whole stack: `docker compose up --build`.

## Environment variables (`.env.example`, values empty)

```
BHARATCODE_API_KEY=
BHARATCODE_BASE_URL=https://bharatcode.ai/api/model/v1
BHARATCODE_MODEL=qwen-3.8-27b
BHARATCODE_TIMEOUT_SECONDS=120
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
DATABASE_URL=sqlite:///./dev.db
FIELD_ENCRYPTION_KEY=
APP_BASE_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Nothing secret may ever use the `NEXT_PUBLIC_` prefix; those values ship to the browser.

## BharatCode API rules

- OpenAI-compatible. Use the `openai` Python SDK with `base_url=settings.bharatcode_base_url` and Bearer auth. Call it only from `llm/client.py`, never from the browser, the web app or bot handlers.
- Model: `qwen-3.8-27b` only (student access, 10M tokens a day). Do not depend on `deepseek-v4.1-flash`; it needs Pro.
- Use the Responses API with `store=False`. It is **stateless**: resend the full history plus `function_call_output` items every turn. `previous_response_id`, `store=True`, hosted tools and background jobs return `400`.
- Structured output: `text={"format": {"type": "json_schema", "name": ..., "schema": ..., "strict": True}}`, schema generated from the Pydantic model. Use `reasoning={"effort": "none"}` for short extraction steps.
- Input is text and images only (no audio, video or files). Convert PDFs to PNG pages with `pypdfium2` before sending.
- Function tools: we execute them. Validate arguments with Pydantic, then return a string output with the matching `call_id`.
- Truncation: Responses `status == "incomplete"` with reason `max_output_tokens` (or Chat Completions `finish_reason == "length"`) is a failure even with HTTP 200. Keep the partial text, never run a partial tool call, retry once with a higher `max_output_tokens` (cap 32,000, reasoning included). Never loop on the same budget.
- `503` means busy: back off 2 s, 4 s, 8 s, then surface a "busy, try again" state. A stream that already started ends with `response.failed`.
- On errors, log the `x-request-id` response header, never the request or response body.
- In code: `build_client(settings)` returns an `LLMClient`; call `await llm.structured(OutputModel, instructions=..., input=...)`. It raises `ModelBusy`, `ModelIncomplete` (with `partial_text`) or `ModelOutputInvalid`; harness steps turn those into "busy, try again" or a question to the user. The SDK's own retries are off (`max_retries=0`) so these rules own retrying.
- Tests fake the API with `httpx2.MockTransport` passed as `build_client(..., http_client=...)`. The `openai` 3.x SDK ships `httpx2`, not `httpx`.

## Harness pipeline

`intake → classify → rewrite → validate → compose → (track) → read_reply → appeal`

- Each step: one prompt file in `src/unseal/prompts/` (front matter `version: N`; placeholders `{language}` and `{glossary}`), one Pydantic output schema in `llm/schemas.py`, one function in `harness/`. Prompts never contain section numbers, fees or deadlines (a test enforces it).
- `compose` fills a Jinja template. The model writes only the subject line and the numbered questions; names and addresses come from the DB at render time.
- Applicant name, address and phone are **never** sent to the model. Reply photos contain personal data: send them only after the user opts in, and keep only the extracted fields.
- Changing a prompt requires bumping its `version` and passing the live golden eval (at least 27 of 30 cases) before merge.

## RTI domain rules

Jurisdictions in v1: `central` and `tamil_nadu`. Languages: `en`, `hi`, `ta` (Section 6(1) allows English, Hindi or the official language of the area).

| Rule | Value | Basis |
| --- | --- | --- |
| PIO reply | 30 days from receipt | S. 7(1) |
| Filed via an Assistant PIO | 35 days (5 added) | S. 5(2) proviso |
| Third party involved | 40 days | S. 11(3) |
| Life or liberty | 48 hours | S. 7(1) proviso |
| Transfer | within 5 days; Act silent on the new period (DoPT Guide: 30 days from new receipt); first-appeal clock stays on the original receipt until decided | S. 6(3) proviso |
| No reply in time | deemed refusal | S. 7(2) |
| First appeal | within 30 days of reply or of due date | S. 19(1) |
| Appellate authority decision | 30 days, extendable to 45 | S. 19(6) |
| Second appeal | within 90 days of decision, or of the FAA deadline passing; late allowed for sufficient cause | S. 19(3) |
| Fee | Rs 10 (central and Tamil Nadu); copies Rs 2 per page, A3 or smaller (central); BPL exempt (S. 7(5)), central needs the BPL certificate copy (r. 5) | RTI Rules 2012 (G.S.R. 603(E)); TN Fees Rules 2005 |
| Length (central) | ordinarily 500 words or fewer; never rejected for length alone | RTI Rules 2012, r. 3 |
| Personal information | exempt as a class since 13 Nov 2025; under Supreme Court challenge | S. 8(1)(j) as amended by DPDP Act s. 44(3) |

Date math conventions (implement in `rules/engine.py`, test every one):
- Calendar days; the day of receipt is day 0, so `due = received_on + timedelta(days=N)`.
- All dates in `Asia/Kolkata`; store `DATE` for days and UTC for timestamps. The 48-hour track uses timestamps.
- Unknown `received_on`: use `filed_on + transit_buffer_days` (default 7) and set `estimated=True`. The UI must show "estimated".
- Payment modes are stored per authority, not per state.
- A rule with `checked_on` older than 180 days shows a "recheck" warning.

Validator flags:
- Asks about another identifiable person's personal information → warn (S. 8(1)(j)) and suggest an aggregate or anonymised version.
- "Why", opinion or advice questions → rewrite into a request for records.
- Over 500 words (central) → warn, never block.
- Missing PIO address or applicant address → block export.

Every generated document ends with: "Prepared with UnSeal. Not legal advice."

## Coding conventions

- Python: type hints everywhere, Pydantic v2, async routes, ruff for lint and format. Business logic lives in `harness/` and `rules/`, not in routes. Inject the LLM client so tests can swap in a fake.
- TypeScript: `strict` on; server components by default; the web app talks only to our API.
- IDs: opaque UUIDv4 in URLs; never put names, phone numbers or case details in a URL.
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

## Testing

- `pytest` runs offline by default using `tests/fixtures/recorded/`; tests marked `live` hit the real API and are opt-in.
- Rules engine: cover 30, 35 and 40 days, 48 hours, transfers, estimated receipt dates, month and year boundaries, and 29 Feb 2028.
- PDFs: render the three golden applications (en, hi, ta), assert the Noto fonts are embedded, and keep the outputs in `tests/golden/pdf/` for visual review.
- Done means: tests pass, ruff is clean, and the diff has no secrets, real personal data or new hardcoded fees or deadlines.

## Security checklist

- A pre-commit hook runs ruff and a secret scanner (gitleaks). Never bypass it with `--no-verify`.
- Before any commit, check `git diff --cached` for keys, tokens and real personal data.
- Applicant fields are encrypted with Fernet via `db/crypto.py`; never store plaintext copies or cache them.
- The Telegram webhook must check the `X-Telegram-Bot-Api-Secret-Token` header against `TELEGRAM_WEBHOOK_SECRET`.
- Rate-limit per user (slowapi). CORS allows only `APP_BASE_URL`.
- `DELETE /me` and `DELETE /cases/{id}` remove rows and stored files; closed cases auto-delete after 180 days.
- Log redaction (`privacy/redact.py`) masks phone numbers, emails and 12-digit ID-like numbers.

## Project skills (`.claude/skills/`)

| Skill | Use it |
| --- | --- |
| `tdd-first` | At the start of every feature, fix or refactor |
| `feature-wiring-trace` | Before building a feature, and before calling it done (both channels, all three languages) |
| `state-machine-feature` | Adding or changing a case status, transition, deadline kind or reminder |
| `rti-rules-research` | Adding or changing anything in `rules/data/*.json`, or a "recheck" warning |
| `never-destroy-data` | Any delete, drop, unscoped write, non-local `DATABASE_URL` or encryption-key change |
| `responsive-design` | Any screen in `apps/web` (phone first, long Tamil and Hindi text) |
| `accessibility` | Any PR touching `apps/web` UI (WCAG 2.1 AA) |
| `staff-engineer-review` | Before calling a change done, opening a PR or merging |
| `deploy-impact` | Before done or a PR: the out-of-band hand-off checklist |
| `pr-create` | Branches, commits, the pre-PR green gate, the PR template |
| `proactive-pentest` | Security audits, and before the 3 Nov and 10 Nov submissions |
| `architecture-decision-records` | A decision that constrains future work (`docs/adr/`) |
| `demo-countdown-plan` | Building or rebuilding the day-by-day plan to 3 Nov and 10 Nov |
| `session-context-sync` | Start and end of every session (`context.md`) |

Hooks (`.claude/settings.json`): format on edit (ruff in `apps/api`, prettier and eslint in `apps/web`), a session-start reminder, and a session-end marker in `.claude/session-log.md`.

## Out of scope (do not build without a PRD update)

- Automating rtionline.gov.in or any government portal: no scraping, form-filling or CAPTCHA solving.
- WhatsApp, payments, voice input, or states beyond Tamil Nadu.
- Government emblems or anything that makes a document look official.
- Hardcoding fees, deadlines or section numbers outside `rules/data/*.json`.

## Hackathon checklist

- The repo is public, `BharatCode.txt` is in the root, and the main repository link is submitted (not a branch or file link).
- Judging uses GitHub stars, BharatCode website votes and the judges' review, so keep the README demo-ready: a one-line pitch, a GIF, "Try it" links for web and Telegram, and setup steps.
- The submission form forbids secrets, tokens, private links and private user data in the repo.
