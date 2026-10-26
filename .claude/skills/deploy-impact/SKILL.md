---
name: deploy-impact
description: Use BEFORE calling any fix or feature done, and before opening or updating a PR in UnSeal. Scans the change for work that must happen outside the code (migrations to apply, env vars and secrets to set, the Telegram webhook to re-register, system libraries or fonts the image needs, rules or prompts that need re-checking) and reports it as an explicit hand-off checklist. Also use when asked "what do I need to do to deploy this".
---

# Deploy impact: what does this change need a human to do?

Most deploy failures are not code bugs. They are "somebody had to do a thing and nobody wrote it
down": an env var never set, a webhook never re-registered, a font missing from the image. This
skill writes it down.

## When to run it
- Before declaring any fix or feature complete, and before opening or updating a PR.
- When a change touches `alembic/`, `config.py`, `.env.example`, `Dockerfile`,
  `docker-compose.yml`, `fonts/`, `prompts/`, `rules/data/`, `bot/`, `scheduler.py`, lockfiles,
  or `.github/workflows/`.

## What to check (walk every row; write "none" where empty)

| Category | What to flag |
|---|---|
| Migrations | Each new Alembic revision; mark any that drop or rewrite data loudly, and say whether it runs before or after the new code |
| Env and secrets | Settings the new code reads that are missing from `.env.example`; new secret names that someone must set on the API host or in Vercel. Any `NEXT_PUBLIC_` var holding a secret is a blocker, not a checklist item |
| Telegram | A changed webhook URL, path or `TELEGRAM_WEBHOOK_SECRET` means the webhook must be re-registered with Telegram |
| Scheduler | APScheduler runs inside the API process. More than one API replica means reminders can fire twice (FR-9 says exactly once): flag replica count changes |
| Image | WeasyPrint needs Pango system libraries; PDF changes need the Noto fonts present in `apps/api/fonts/` inside the image. A Dockerfile change needs a rebuild |
| Rules data | A changed rule in `rules/data/*.json` has a fresh `source_url` and `checked_on`, and the PRD and CLAUDE.md tables match (skill `rti-rules-research`) |
| Prompts | A changed prompt has a bumped `version` and a passing live golden eval |
| Web | API contract changes reach the web app and the bot in the same PR; `NEXT_PUBLIC_API_URL` and `APP_BASE_URL` (CORS) still match the deployed hosts |
| Dependencies and CI | Changed `uv.lock` or `package-lock.json` means an install; changed workflows mean a changed gate |

## How to report it
Put the checklist at the **end** of the work, as actions the user can take, each with the file
that caused it. Split **before this ships** (migrations, secrets, webhook) from **local dev only**
(re-run install, restart the API). If nothing applies, say: "code-only change, nothing to do out
of band."

## What a diff cannot show (add these yourself)
- A secret value that must be set on the API host or in Vercel (the diff shows only the name).
- Telegram BotFather settings, DNS, domains, certificates.
- The BharatCode daily token budget during a demo or voting spike.
- A one-off backfill and its order relative to the deploy.
- Anything agreed in conversation rather than written in code.

## Honesty rule
Report what you found. Do not add plausible items you did not verify; if an item comes from your
own knowledge of the change rather than the diff, say so.
