---
name: tdd-first
description: Use at the START of every feature, bugfix, or refactor in UnSeal. Enforces test-first (RED, GREEN, REFACTOR) with 80%+ coverage and maps it to the stack - pytest with recorded model responses for the harness, exhaustive date cases for the rules engine, golden PDFs for rendering, Playwright screenshots for UI.
---

# TDD First

Always start test-first. Announce it: "Starting TDD: writing the failing test first." Show the RED
output and the GREEN output in the conversation (user rule).

## Loop
1. **RED**: write the smallest test that captures the next behaviour. Run it; it must fail for the
   right reason (an assertion, not an import error).
2. **GREEN**: minimal code to pass. Nothing speculative.
3. **REFACTOR**: clean up with tests green.
4. Repeat. Check **80%+ coverage** on changed code before calling it done.

## Stack mapping
- **Rules engine** (`rules/engine.py`, `rules/data/*.json`): pure functions, so test them
  exhaustively and aim for 100%. Every path in CLAUDE.md gets a case: 30, 35 and 40 days, 48 hours
  (timestamps), transfers under S. 6(3), estimated receipt dates (`estimated=True`), month and
  year boundaries, 29 Feb 2028, and the 180-day "recheck" warning. A new rule in JSON starts as a
  failing engine test.
- **Harness steps** (`harness/`): the LLM client is injected, so tests use a fake that replays
  `tests/fixtures/recorded/`. Cover: valid output, schema-invalid output (retry once, then ask the
  user), truncated output (`status == "incomplete"`, never run a partial tool call), and 503
  backoff. Tests never hit the network unless marked `live`.
- **Prompts**: a prompt change starts by adding or updating golden cases in `tests/golden/`, then
  bumping the prompt's `version`, then passing `uv run pytest -m live tests/golden` (27 of 30).
- **Validator**: one test per flag (personal information, opinion or "why", over 500 words,
  missing PIO or applicant address blocks export).
- **PDF** (`pdf/`): render the golden application per language (en, hi, ta), assert the Noto fonts
  are embedded and the "Prepared with UnSeal. Not legal advice." footer is present; keep outputs
  in `tests/golden/pdf/` for visual review.
- **Privacy**: redaction and crypto have unit tests (`tests/unit/`): phone numbers, emails and
  12-digit ID-like numbers are masked; encrypted fields round-trip and are not stored in plaintext.
- **API routes**: FastAPI `TestClient`. Every route that takes a case id gets a negative test
  (another user's case returns 404, not the data).
- **Web** (`apps/web`): no unit runner chosen yet. UI changes get a Playwright check with
  screenshots (user rule). When a runner is added, record it in CLAUDE.md.

## Non-negotiable
- Bug fix: first write a test that reproduces the bug, then fix it.
- Fixtures use fictional applicants only. A real name, phone or address in a fixture is a finding.
- Never weaken, skip or delete a test to go green. Loosening a golden expectation needs a stated
  reason in the PR.

## Prove the test can fail
AI-written tests can be tautological. For critical logic (rules engine, validator, crypto,
deletion), revert the change, confirm the test goes red, restore it. If nothing breaks, the test
is weak: strengthen it.
