---
name: demo-countdown-plan
description: Use when UnSeal must be demo-ready by a fixed date and you need to build or rebuild a dated day-by-day plan to the 3 Nov MVP submission and the 10 Nov 11:59 PM IST close, with sized tasks, a reserved dry run, a launch checklist and a cut line.
---

# Demo Countdown Plan

A deadline is a hard wall. The plan is built **backwards from the wall**, never forwards from today.
It produces one artifact: a dated task table, a cut line and a short risk register, sized so a slip
shows on the day it happens. Use it to (re)build the plan on request, not as a fixed calendar. It
decides *which day each task lands on*; `docs/PRD.md` decides *what* the tasks are.

## Step 1: pin the anchors

Resolve the calendar first: `date +"%Y-%m-%d %A"`, `git log --oneline -10`, `git status --short`
(no code existed on 26 Oct 2026; re-check before reusing that). Then confirm with the user:

1. **Walls.** Target MVP submission 3 Nov 2026; close 10 Nov 2026, 11:59 PM IST. Use IST throughout.
2. **Team and hours.** The PRD leaves "who owns API, web, bot and PDFs" open. Without owners and
   hours per day the plan is fiction; mark owners `TBD` and say so.
3. **Open questions.** What `BharatCode.txt` must contain (ask the organisers) and whether the name
   "UnSeal" clashes with an app or trademark. Both are cheap to settle on day 1.

## Step 2: the dependency order

```
language fallback eval + rules JSON   (days 1 and 2: "everything else builds on them")
  -> rules engine + tests (FR-6), LLM client -> harness: intake, classify, rewrite, validate (FR-1 to FR-4)
  -> PDF in en, hi, ta (FR-5) -> tracker (FR-7) -> delete and export (FR-8) -> first deploy
  -> all eight P0 green -> freeze -> dry run -> submit -> P1s, polish, votes
```

- **All eight P0 FRs (FR-1 to FR-8) before any P1.** Start a P1 only when every P0 passes.
- **Check the demo script and launch checklist against the priorities.** Demo step 4 needs the reply
  reader and first appeal drafter (FR-10, FR-11) and the checklist needs the sample gallery (FR-13),
  all P1. Decide on day 1 and write it down: pull them forward as the first P1s, or show them from
  cached sample cases and finish after 3 Nov. Then order the rest (FR-9, FR-12).
- Rule values come from `rules/data/*.json` with `source_url` and `checked_on`; use `rti-rules-research`.

## Step 3: size every task, spike the riskiest unknown on day 1

1. **No task over four hours** (one that cannot be split is the spike), each marked demo-critical or
   nice-to-have. If the 90-second script does not touch it, it never goes ahead of demo-critical work.
2. **The spike is the Tamil and Hindi eval**: 10 prompts per language on `qwen-3.8-27b`, first slot
   of day 1. Agree the pass bar first (the PRD sets none). It ends in a written verdict, not code:
   pass, or the fallback (compose in English, translate, show both for review, fixed legal phrases
   in templates). No verdict by the timebox means take the fallback on day 1.

## Step 4: hosting is a scheduled human action

Web on Vercel; API as a Docker image on any container host. Nothing more is decided, so schedule a
row to **pick the container host** and one for the **first deploy**, early enough that the "Try it"
links exist before the dry run. UnSeal traps:

- WeasyPrint needs Pango system libraries: test the three golden PDFs **inside the image** and
  confirm Noto fonts are embedded.
- Production env vars and the Telegram webhook secret are set by name on the host; values never
  enter the repo, chat or logs. The bot runs in webhook mode inside the API service: smoke-test it.
- Never deploy in the last four hours before a dry run or a submission.

## Step 5: the dry run is a reserved day, never a build day

Reserve the full day before submission and freeze code the evening before. That day holds only the
following. Anything found on it is a cut-line decision, not a fix.

- The **90-second demo script**, start to finish, on the deployed stack, in Tamil on Telegram, timed,
  fictional applicants only. Then a second run, since the first leaves state behind.
- Negative paths: a missing PIO address blocks export, a 503 shows "busy, try again", `DELETE /me`
  removes every row and file.
- Gates green: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`; in `apps/web`
  `npm run lint` and `npm run build`; the live golden eval (`uv run pytest -m live tests/golden`)
  at 27 of 30 or better.
- Recording the GIF and the demo video (2 minutes or less) from the working build.

## Step 6: the launch checklist

- [ ] `BharatCode.txt` in the repo root; repo public; the main repository link is submitted (not a branch or file link)
- [ ] README: one-line pitch, 30-second GIF, "Try it" links (web and Telegram), architecture picture, setup steps
- [ ] Repo description, topics and MIT license set; demo video (2 minutes or less) linked from the README
- [ ] Sample gallery live so voters can try it without typing personal data
- [ ] No secrets, tokens, private links or real personal data in the repo (the form forbids them)
- [ ] Links shared: the repo to star, the Build League page to vote

## Step 7: the cut line

Write it on day 1 and drop strictly top-down:

1. Nice-to-have polish: empty states, animation, copy tuning.
2. P1s the demo and launch do not use (FR-9, FR-12; the team picks the order).
3. Live model calls in the demo: show cached output for sample cases (PRD mitigation for the daily
   token cap and 503s). Build the cache early; an untested cache is not a fallback.
4. Live reply reading and appeal drafting: show them from sample letters.

**Never cut:** the eight P0s, `BharatCode.txt`, rules from the JSON with sources, the "Not legal
advice" footer, no real personal data. **After 3 Nov a slip costs features, not the entry**, because
the MVP is already submitted. A slip *before* 3 Nov moves the submission day, never the 10 Nov close;
each day lost is a day without stars and votes. Treat 9 Nov as the last planned submission day.

## Output template (worked example from 26 Oct 2026; one row per day, resize to the real team)

| Date | Tasks (hours, each four or less) | Blocked by |
|------|----------------------------------|------------|
| Mon 26 Oct | SPIKE Tamil and Hindi eval, 10 prompts each (3); `central.json` with `source_url`, `checked_on` (4); settle `BharatCode.txt` and name (1) | |
| Tue 27 Oct | Record language decision (2); `tamil_nadu.json`, payment modes per authority (4); repo scaffold, MIT license, `.env.example` (2) | spike |
| Wed 28 Oct | `rules/engine.py` + tests: 30, 35, 40 days, 48 hours, 29 Feb 2028 (4); `llm/client.py`, schemas, fixtures (4) | JSON |
| Thu 29 Oct | Intake and classify on web (4); Telegram handler (4), both FR-1 | client |
| Fri 30 Oct | Rewriter + golden set, FR-2 (4); validator, FR-3 (4); authority routing, FR-4 (4) | intake |
| Sat 31 Oct | PDF in en, hi, ta, FR-5 (4); pick host, first deploy, smoke test (4) | validator |
| Sun 1 Nov | Tracker + dashboard, FR-7 (4); delete and export, FR-8 (2); live golden eval; CODE FREEZE 18:00 IST (2) | all P0 |
| Mon 2 Nov | DRY RUN twice on the deployed stack, negative paths (4); GIF, video, README (3) | freeze |
| Tue 3 Nov | Launch checklist; **submit the main repo link**; share both links (3) | dry run |
| Wed 4 to Sun 8 Nov | P1s: FR-10, FR-11, FR-13, then FR-9, FR-12; polish; vote push; P1 freeze Sun 18:00 IST | submitted |
| Mon 9 Nov | Final dry run; repo public, link valid, no secrets (3) | freeze |
| Tue 10 Nov | Buffer only. Closes 11:59 PM IST | |

| Risk | Detected by | Mitigation | Fallback |
|------|-------------|------------|----------|
| Weak Tamil or Hindi output | spike, 26 Oct | day-1 eval | English first, translate, show both |
| PDFs break inside the image | first deploy, 31 Oct | test fonts in the image | pre-rendered golden PDFs |
| Token cap or 503s during voting | dry run, 2 Nov | backoff, "queued" state | cached sample cases |
