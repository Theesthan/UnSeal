---
name: staff-engineer-review
description: Use before committing, opening a PR or merging any UnSeal change, and when reviewing another agent's diff. Scores the diff PASS/WEAK/FAIL against the repo's own rules (code owns dates and fees, no secrets, no personal data, validated model output) and ends with a verdict.
---

# Staff Engineer Review

Review the diff against UnSeal's own rules (`CLAUDE.md`, `docs/PRD.md`), not generic taste. Score only the checks the diff touches and mark the rest N/A. Every WEAK or FAIL cites `file:line` and a concrete fix.

## Run it

1. Read the staged and unstaged diff and the code around each hunk. Do not stage or commit as part of the review.
2. Grep the diff for the red flags under each check before scoring.
3. Run what applies and say what you ran.
   - From `apps/api`: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`.
   - From `apps/web`: `npm run lint`, `npm run build`.

## Checks

**Legal correctness and model use**

1. **Code owns dates, fees, sections.** FAIL if the model computes or is trusted for any of them.
   - FAIL if one is hardcoded outside `rules/engine.py` and `rules/data/*.json`.
   - Red flags: literals such as 30, 35, 40, 48, "Rs 10", "S. 7" in `harness/`, `prompts/`, `bot/`, `pdf/`, `apps/web`.
   - Engine: calendar days, receipt is day 0, `Asia/Kolkata`, estimated dates flagged, every rule keeps `source_url` and `checked_on`.
2. **Output validated.** Every model output is parsed by its Pydantic model in `llm/schemas.py`.
   - The strict JSON schema is generated from that model; one retry, then ask the user.
   - FAIL on raw model text used for control flow, for a date, or put into a PDF unvalidated.
3. **Truncation and 503.** `status == "incomplete"` or `finish_reason == "length"` is a failure even on HTTP 200.
   - Keep the partial text, never run a partial tool call, retry once with a higher `max_output_tokens` (cap 32,000), never loop on one budget.
   - A 503 backs off 2, 4, 8 s, then shows "busy, try again". Errors log `x-request-id`, never bodies.
4. **BharatCode client rules.** Only `llm/client.py` calls BharatCode (not the browser, web app or bot handlers).
   - `store=False`, full history replayed each turn, no `previous_response_id`, hosted tools or background jobs.
   - Model is `qwen-3.8-27b` only.
5. **Prompt changes.** `version` bumped in the prompt front matter, live golden eval run (at least 27 of 30), recorded fixtures refreshed. FAIL if a prompt changed with no bump.

**Privacy and security**

6. **No secrets.** None in code, tests, fixtures, logs, commits or PR text.
   - `.env.example` has empty values; any new env var is added there by name.
   - Nothing secret behind `NEXT_PUBLIC_`.
7. **No personal data leaks.** Real personal data lives only in the encrypted DB.
   - Not in logs, URLs (opaque UUIDv4 only), analytics, fixtures, prompts or screenshots. Fictional applicants only.
   - New log lines still pass through `privacy/redact.py`.
8. **Model sees the minimum.** Applicant name, address and phone are never in a model call.
   - Each step gets only what it needs (the rewriter sees questions, not addresses).
   - Reply photos go out only after opt-in, and only the extracted fields are kept.
9. **Encryption and deletion.** Applicant fields and `telegram_chat_id` go through `db/crypto.py` (Fernet), with no plaintext copies or caches.
   - A new table or stored file is covered by `DELETE /me`, `DELETE /cases/{id}` and the 180-day auto-delete.
   - Schema changes ship as an Alembic revision.
10. **Endpoint hardening.** The Telegram webhook checks `X-Telegram-Bot-Api-Secret-Token` against `TELEGRAM_WEBHOOK_SECRET`.
    - Per-user rate limit (slowapi); CORS allows only `APP_BASE_URL`.
    - Requests aimed at a named private individual are refused.

**Product, repo and scope**

11. **Documents.** Every generated document ends with "Prepared with UnSeal. Not legal advice." in `en`, `hi` and `ta`.
    - No emblems or official look; Noto fonts embedded.
    - The validator warns, and blocks only on a missing PIO or applicant address.
    - Estimated dates say "estimated"; rules older than 180 days say "recheck".
12. **Repo hard requirements.** `BharatCode.txt` is still in the repo root and untouched. No `--no-verify`; the ruff and gitleaks pre-commit hook is intact.
13. **Scope.** FAIL on anything on the out-of-scope list.
    - Scraping, form-filling or CAPTCHA work on rtionline.gov.in or any portal; WhatsApp; payments; voice input; states beyond Tamil Nadu; government emblems.
    - WEAK if P1 work lands while a P0 is incomplete, or scope moved without a PRD edit first.
14. **Layering and tests.** Business logic sits in `harness/` and `rules/`, not routes; the LLM client is injected so tests use a fake.
    - Type hints, TypeScript `strict`, and the web app talks only to our API.
    - Tests run offline from `tests/fixtures/recorded/`; at least one test fails without the change.
    - Engine changes cover 30, 35, 40 days, 48 hours, transfers, estimated dates, month and year ends, 29 Feb 2028.

## Output

A table, then a verdict. Any FAIL blocks the merge. A WEAK needs a fix or a written reason.

| # | Check | Verdict | Evidence (`file:line`) | Fix |
|---|-------|---------|------------------------|-----|
| 1 | Code owns dates, fees, sections | PASS / WEAK / FAIL / N/A | where you looked | concrete change, or n/a |

**Verdict:** SHIP, FIX FIRST or BLOCK, then one or two lines naming the single highest-leverage change. Lead with any FAIL on checks 1 to 10, since the test suite rarely catches those.

## Anti-patterns to name

- The model writing "due in 30 days" or a section number into user-facing text.
- A retry loop on the same `max_output_tokens`, or logging a request or response body on error.
- A "temporary" real name, phone number or ID in a fixture or screenshot.
- A template or component that carries its own copy of a fee or deadline instead of the engine's value.
- A feature built for the web app only, or for `en` only, when FR-1 needs both channels and all three languages.
