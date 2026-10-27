---
name: state-machine-feature
description: Use before adding or changing a case status, a transition, a deadline kind or a reminder in UnSeal. Keeps the case lifecycle (draft to closed) explicit and idempotent, takes every date from the rules engine, and makes each reminder fire exactly once.
---

# Case Lifecycle State Machine

FR-7 gives `cases.status` this order: draft, filed, reply due, replied or deemed refused, appealed, closed. Dates live in `deadlines` (`pio_reply`, `first_appeal`, `faa_decision`, `second_appeal`) and always come from `rules/engine.py`. No workflow engine or queue: a status column, the engine, and the 15-minute APScheduler job.

## Transitions (a reading of FR-7; confirm before coding)

| From | To | Trigger | Deadline effect (engine) |
|---|---|---|---|
| draft | filed | user logs filing date and mode | none yet |
| filed | reply due | `received_on` known, or estimated with the transit buffer | creates `pio_reply` |
| reply due | replied or deemed refused | reply logged (typed or photographed), or `pio_reply` passed with no reply (S. 7(2)) | creates `first_appeal` window |
| replied or deemed refused | appealed | first appeal drafted (S. 19(1)) | creates `faa_decision` |
| replied or deemed refused, appealed | closed | user closes the case | none; starts the 180-day retention clock |

Events that move deadlines but not status: a transfer (S. 6(3)); the appellate authority's decision being logged or its deadline passing (opens `second_appeal`, S. 19(3)); a second appeal being drafted.

## Enforce the map

- A transition names the status it expects and writes with `UPDATE ... WHERE id = ? AND status = ?`. Zero rows updated means illegal or already applied. Never read, then write.
- Repeating a legal transition is a no-op that returns the same result: no duplicate `deadlines` or `documents` rows, no second reminder. A double tap on a Telegram button or a webhook redelivery must be safe.
- Any other illegal transition is a clear 4xx (409 for a state conflict) on the API and a plain-language reply in the user's language on the bot. Never a silent overwrite.
- `closed` is terminal. No reopen without a PRD change.
- Never infer status from a side effect ("the PDF exists, so it is filed"). The column is the truth.
- Deleting is not a transition: `DELETE /cases/{id}` works from every status.

## Dates come only from the engine

- Handlers pass anchor dates in and store what `rules/engine.py` returns. Routes, bot handlers and the web app never add days. Appeal anchors (reply date, appeal filing date, decision date) are engine inputs, tested like the rest.
- Unknown `received_on`: `filed_on` plus the transit buffer (default 7), `estimated=True`, shown as "estimated". When the real date is logged, recompute and clear the flag.
- Transfer: the case stays `reply due`. Record the transfer and the new authority's receipt date, but keep the user's `pio_reply` and `first_appeal` deadlines on the ORIGINAL receipt (`rules.deadlines.transfer_deadlines`): the Act is silent on the new clock, so the conservative default protects the appeal window (see the `transfer` note in `rti_act.json`). Show the new authority's expected reply as information only.
- Life or liberty: the 48-hour track uses UTC timestamps, not the `DATE` logic.
- A date the model read from a reply photo is a proposal. Validate it with Pydantic and have the user confirm it before it anchors a deadline.
- A late first appeal is still draftable; show that it is late (the appellate authority has discretion).
- Where the due date itself falls (still in time or overdue) is decided once in the engine and tested.

## Reminders fire exactly once (FR-9)

Windows are 7 days before, 1 day before, and on the due date, per deadline, on Telegram and web.

- The job runs every 15 minutes, so each window is seen many times. Claim before sending: a conditional update that sets the sent marker `WHERE` it is still unset, and send only if one row changed. On a definite send failure, clear that marker so the next tick retries.
- Several API processes may each run a scheduler. The conditional claim, not the schedule, is what guarantees once. Also set the job to a single instance and coalesce missed runs.
- Skip closed cases and replaced deadlines. A recomputed due date resets only its own markers.
- Take "today" from an injected clock in `Asia/Kolkata`, so tests can pin it.

## Web and Telegram

- The timeline reads status and deadlines from the API, never recomputes them, and renders every status, in `en`, `hi` and `ta`, on both channels. An unknown status shows a clear fallback, never a blank card.
- Show "estimated" on estimated dates and the "recheck" warning on rules older than 180 days.

## Adding a status or transition

1. Update `docs/PRD.md` (FR-7) first, then `CLAUDE.md`, then the table above.
2. Alembic revision for any new column, additive.
3. Handle it in the route, the bot, the web timeline and the reminder job. An unhandled status reads as a broken app.
4. Test every legal edge, every illegal edge, and the repeat of each legal one.

## Tests

- [ ] Each legal edge; each illegal edge errors and writes nothing; each legal edge twice creates nothing new.
- [ ] Transfer replaces the `pio_reply` row; estimated to actual recomputes.
- [ ] Two scheduler ticks, and two concurrent ones, send a reminder once. A closed case sends none.
- [ ] Engine dates at 30, 35, 40 days, 48 hours, month and year ends, and 29 Feb 2028.

## Open questions (resolve in the PRD, not in code)

- Is "replied or deemed refused" one status or two? Is a `transferred` status needed? This skill treats transfers as events and `appealed` as covering both appeals; first versus second stays visible through deadline kinds.
- Data model gaps: `deadlines.notified_at` is one timestamp but FR-9 sends three reminders per deadline, and `cases` has no closed-on date for the 180-day retention.
