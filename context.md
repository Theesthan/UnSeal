# UnSeal: living repo state

Read at session start; update at session end (skill `session-context-sync`). A map, not a
changelog: keep it short.

## Where things stand (2026-10-26)

Repo bootstrapped: `docs/PRD.md`, `CLAUDE.md`, `.claude/` (skills, hooks, settings),
`.gitignore`, `.env.example`. No application code yet.

## In progress
- Day 1 and 2 (PRD build plan): Tamil and Hindi quality eval on `qwen-3.8-27b` (10 prompts per
  language) and the rules JSON (`rules/data/central.json`, `rules/data/tamil_nadu.json`).

## Done
- 2026-10-26 Product renamed from RTI Saathi to UnSeal (package `unseal`).

## Open
- `BharatCode.txt` contents unknown: ask the organisers (PRD open questions).
- Team split across API, web, bot and PDFs.
- Trademark check for "UnSeal".
- Data model gaps to settle in the PRD before coding FR-7 and FR-9: `deadlines.notified_at` is
  one timestamp but FR-9 sends three reminders per deadline; `cases` has no closed-on date for the
  180-day auto-delete; "replied or deemed refused" as one status or two; whether `transferred` is
  a status or an event.
- CLAUDE.md says keep only extracted fields from reply photos, but the PRD data model has a
  `documents` row of kind `reply_image`: decide which wins.

## Key decisions
- 2026-10-26 Name: UnSeal; Python package `unseal`; footer "Prepared with UnSeal. Not legal advice."
