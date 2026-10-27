# UnSeal: living repo state

Read at session start; update at session end (skill `session-context-sync`). A map, not a
changelog: keep it short.

## Where things stand (2026-10-27)

Every FR has code on branch `feat/central-rules-json` (pushed, no PR yet). CI
(`.github/workflows/ci.yml`) is green: API lint, types and tests; PDF rendering in Docker; migrations
on Postgres; web lint, unit, build and e2e. No deploy yet.

- API (`apps/api`): sessions (ADR 0003), cases, intake with curated authority candidates, reference
  routes, rewrite and validation, application PDF, filing and deadlines, reply, receipt correction,
  first appeal (FR-10), reply reader from a photo (FR-11), FAA decision and second appeal in the CIC
  or TNSIC format (FR-12), delete and export (FR-8), scheduler (deemed refusal, 180-day retention,
  reminders), Telegram bot with reminders (FR-1, FR-9).
- Web (`apps/web`): the full flow in en, hi, ta, case page with appeal and reply reader, my data, a
  static sample gallery (FR-13), same-origin `/api` proxy.
- Contract: `docs/api.md`.

## In progress
- PR from `feat/central-rules-json` to `main`: waiting on the go-ahead.
- Deploy: API image (`--target runtime`) on a container host, web on Vercel or similar with
  `API_ORIGIN`; `setWebhook` with `secret_token`; check the host's proxy timeout and body limit
  against slow model calls and 10 MB uploads.

## Done
- 2026-10-26 Rules data (`rti_act.json`, `central.json`), engine, BharatCode client, schemas,
  prompts v1, the Tamil and Hindi eval harness.
- 2026-10-27 Prompts v2 with the verified RTI glossary: term errors 7 to 0 (Tamil), 2 to 0 (Hindi).
- 2026-10-27 `tamil_nadu.json`, curated authorities (16), deadlines, DB with migrations 0001 to
  0005, PDFs, API, bot, web, CI. P0 FR-1 to FR-8 and P1 FR-9 to FR-13 built.
- 2026-10-27 Reply reader live check: `qwen-3.8-27b` read a fictional typed letter (date, three
  statuses, s. 8(1)(j)) correctly in about 20 s.

## Open
- `BharatCode.txt` is not in the repo root (hackathon requirement): get it from the organisers.
- Rotate the BharatCode key (pasted into a chat on 2026-10-26).
- Native-speaker review: Hindi and Tamil strings marked in `pdf/*labels.py`, `bot/texts.py`,
  `apps/web/messages/{hi,ta}.ts`; the eval's T and L scores; three low-confidence Tamil glossary
  terms; reconstructed lines in `pdf/tnsic_labels.py`; the TNSIC reason mapping in
  `pdf/second_appeal.py`.
- Rules sign-off: UNASSIGNED. Still OPEN: the TN Information Commission (Appeal Procedure) Rules
  text; S. 7(3)(a) and S. 7(6) are not modelled; Supreme Court orders on W.P.(C) 177/2026 unread.
- Reply reader: the PRD asks for 5 sample letters; 1 is tested live. HEIC photos are unreadable.
- Single replica only: the rate limiter, bot conversation state and webhook dedupe live in memory.
- BharatCode latency was 80 to 300 s per call on 2026-10-27; the web proxy allows 180 s.
- The bot does not yet record replies, receipts or appeals (the web does).
- Web unit coverage 50.6% (flow screens covered by e2e only); the 80% target is not met.
- Trademark check for "UnSeal".

## Key decisions
- 2026-10-26 Name: UnSeal; Python package `unseal`; footer "Prepared with UnSeal. Not legal advice."
- 2026-10-26 ADR 0001: statute rules once in `rti_act.json`; jurisdiction files hold only their own rules.
- 2026-10-27 ADR 0003: anonymous sessions; only token hashes and HMACed chat ids are stored.
- 2026-10-27 Appeals make no model call: dates, filing mode and grounds are template text (a
  recorded `appeal_facts` run turned a postal filing into an email).
- 2026-10-27 Reply photos are never stored: CLAUDE.md wins over the PRD's `reply_image` row.
- 2026-10-27 Status set: `replied` and `deemed_refused` are separate; a transfer is an event.
- 2026-10-27 The intake server keeps no history: clients send the whole conversation each turn.
- 2026-10-27 Search text never goes in a URL (`POST /authorities/search`).
- 2026-10-27 Second appeal fields UnSeal does not hold print blank; the forms are not shortened.
