---
name: session-context-sync
description: Use at the start and end of every working session in UnSeal, and after pulling or switching a branch. Keeps context.md and CLAUDE.md current so each session resumes with full state instead of re-discovering it.
---

# Session context sync

`context.md` (repo root) is the living map of what exists and what is in flight. Keep it true.

## At session start
1. Read `context.md` and the tail of `.claude/session-log.md` (if present).
2. The SessionStart hook prints the branch. If it changed since the last session, or you just
   pulled, reconcile `context.md` with what is actually on this branch before doing work.
3. Check the date against the deadlines in CLAUDE.md (MVP 3 Nov, close 10 Nov 11:59 PM IST). If
   the plan has slipped, run skill `demo-countdown-plan`.

## During and at session end
Update `context.md`:
- Move finished items from **In progress** to **Done**, with the FR ids they close.
- Add new in-flight work to **In progress** (branch, PR link, what is left).
- Append a dated line to **Key decisions** for any decision made this session. If it constrains
  future work, write the ADR too (skill `architecture-decision-records`).
- Link any doc written.

Keep it short: it is a map, not a changelog. Mechanical markers (time, branch, commit) are
appended to `.claude/session-log.md` by the SessionEnd hook; never copy them into `context.md`.

## Index discipline
- A skill, rule or doc added this session gets its one-line pointer in CLAUDE.md.
- Scope or rule changes go to `docs/PRD.md` first, then CLAUDE.md, in the same change.
- Dated session state lives in `context.md`, never in CLAUDE.md.
