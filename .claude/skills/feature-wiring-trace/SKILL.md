---
name: feature-wiring-trace
description: Use before writing code for any new UnSeal feature, field, rule, harness step or reminder, and before calling one done. Maps every layer it must attach to (rules JSON through to the PDF and tests, web and Telegram, en/hi/ta) and proves it actually runs, not just exists.
---

# Feature Wiring Trace

**The failure this stops:** the code exists, the column is in the DB, the string is in the template, and nothing connects them, so the feature never runs. It typechecks and may even have a test. In UnSeal the usual victims are a feature built for the web and forgotten on Telegram, a string added in `en` only, a rule in JSON that no engine function reads, and a reminder the scheduler never queries. "Wired" is not "runs".

## Step 1: Link map (before coding)

Write this list down first. Ask in order:

1. **Who writes it?** Every producer: a harness step, a route, a bot handler, the scheduler. Personal fields go through `db/crypto.py`.
2. **Who reads it?** Trace to the decision. Does the value change an outcome (a deadline, a flag, a PDF line, a reminder), or does it just sit in a column? A new rule in `rules/data/*.json` must be read by a named function in `rules/engine.py`, for both `central` and `tamil_nadu`.
3. **What enforces it?** A validator flag nothing surfaces, or a schema nothing parses, is decoration. Name the enforcement point, or say there is none.
4. **Who dispatches it?** A route is registered in `main.py`. A bot handler is registered in `bot/`. A scheduler job exists and queries the new deadline kind. A new function tool is exposed to the harness and returns its `function_call_output` with the matching `call_id`. Grep for the registration line.
5. **What must the user see?** On the web app and in Telegram, in `en`, `hi` and `ta`. Each channel and each language is a separate place to forget.
6. **Where does it leave the system?** The PDF, logs (redacted), model prompts (never applicant name, address or phone), and the delete paths (`DELETE /me`, `DELETE /cases/{id}`).

Red flag: you cannot name the line where the value changes a decision. Then it does not.

## Step 2: The chain (no gaps)

```
rules/data/*.json       new rule: source_url, checked_on, central and tamil_nadu
  -> rules/engine.py    pure function, unit-tested at the boundaries
  -> db models + Alembic revision    encrypted if personal, covered by delete
  -> harness step       prompts/<step> (bump version) + schema in llm/schemas.py + function in harness/
  -> llm/client.py      only BharatCode caller; store=False; truncation and 503 paths
  -> FastAPI route      thin: validate, call harness or rules, rate limit
  -> web (Next.js) AND bot/ handler    both call our API; same behavior; en, hi, ta strings
  -> pdf/templates/*.html.j2           all three languages, Noto font embedded, footer present
  -> scheduler.py       reminder query and a sent marker
  -> tests              unit, golden, tests/fixtures/recorded
```

Notes that cost hours when skipped:
- A field missing from the Pydantic model is missing from the strict JSON schema, so the model cannot return it. Change schema and prompt together, and bump the prompt `version`.
- A changed prompt makes recorded fixtures stale and needs the live golden eval (at least 27 of 30).
- A new env var needs `config.py` and `.env.example` (name only, empty value).
- A fee or deadline shown in the web app, bot or PDF must be the engine's value passed through the API, never a number typed into a component.
- Migrations: `uv run alembic revision --autogenerate -m "<what changed>"`, then `uv run alembic upgrade head`. Local SQLite working is not proof for Postgres.

## Step 3: Prove it runs

A passing test proves nothing unless it could have failed.

1. **Break it on purpose.** Revert your change locally, run the new test, confirm it FAILS, then restore. If the API or bot process does not reload, restart it first: a stale process makes the revert prove nothing.
2. **Use the real path.** Run the API (`uv run uvicorn unseal.main:app --reload --port 8000`), drive a fictional case through the web app and through the bot (`uv run python -m unseal.bot --polling`), then read back what the DB stored and what the PDF contains.
3. **Check the decision, not the presence.** Not "the row has a value" but "the deadline has the right `due_on`", "the PDF shows the Tamil text and the footer", "the reminder was sent once".
4. **Distrust vacuous passes.** Recorded fixtures that never reach the new branch. A fake LLM that only returns success, so the retry and failure paths never run. A reminder test whose query returns zero rows.
5. **Offline first.** `uv run pytest -q`. Run `uv run pytest -m live tests/golden` only for prompt changes.

## Step 4: Write down the gaps

In the PR description, list what is deliberately not wired yet and why, plus the test that fails without the change. A known gap written down is fine; an unknown one is a bug. If the feature changes scope, update `docs/PRD.md` first, then `CLAUDE.md`.

## Common breaks

| Symptom | Usually |
|---|---|
| Works on Telegram, not on the web (or the reverse) | Logic sits in a handler or route instead of `harness/` or `rules/`, or one channel's handler was never added |
| Hindi or Tamil text broken, or a string shows in English | Template has no branch for the language, string missing in `hi` or `ta`, or the Noto font is not embedded |
| Model output rejected, or a field is missing | `llm/schemas.py` and the prompt disagree, or the field is absent from the strict schema |
| Recorded tests pass, live eval fails | Prompt changed with stale fixtures, or no version bump |
| Reminder never sent, or sent twice | Job does not query the new deadline kind, or the sent marker is written after sending instead of claimed before |
| Wrong or hardcoded deadline on screen | A component or template carries its own number instead of the engine value |
| Works on `dev.db`, fails on a fresh checkout or Postgres | Missing Alembic revision, or an env var missing from `config.py` and `.env.example` |
| 404 on a new route | Route not registered in `main.py`, or the prefix is doubled |
| Data survives `DELETE /me` | New table or stored file not covered by the delete path |

## Definition of done

- [ ] Producer, reader, enforcement point and dispatcher named in code, not in the abstract.
- [ ] Chain walked with no gap, on both channels and in `en`, `hi` and `ta`.
- [ ] A test that fails without the change, verified by reverting it.
- [ ] Prompt `version` bumped and live golden eval run if any prompt changed.
- [ ] The diff has no new secret, real personal data, or hardcoded fee or deadline.
- [ ] Delete paths cover any new data.
- [ ] Deliberate gaps written down in the PR description.
