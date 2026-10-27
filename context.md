# UnSeal: living repo state

Read at session start; update at session end (skill `session-context-sync`). A map, not a
changelog: keep it short.

## Where things stand (2026-10-26)

Repo bootstrapped: `docs/PRD.md`, `CLAUDE.md`, `.claude/` (skills, hooks, settings),
`.gitignore`, `.env.example`. `apps/api` exists with the rules data and loader only.

## In progress
- Branch `feat/central-rules-json`: central rules done; next `tamil_nadu.json` (TNSIC fee rules).
- Tamil and Hindi eval, first live run (2026-10-27, 1 run per case): both languages pass every
  automated gate (`docs/eval/language-eval-results-*.md`). Needs native-speaker T and L scores,
  then ADR 0002. Claude's non-binding read: structure and tasks mostly right; legal terms often
  wrong (HI "अनुकृप्य", "दिखाने-कहने का नोटिस", "जन-संस्था"; TA "வேலைத்தட்டு" for work order,
  "சான்றிதழ் நகல்" for certified copy) and TA-2's reason says officers ARE obliged to explain.
  Likely fix: prompt v2 with a fixed RTI glossary, or the template-owned-terms fallback.
- BharatCode latency 2026-10-27: 80 to 100 s per call, some calls over 5 min; models.list 0.3 s.
  Demo needs cached sample outputs and a "queued" state (PRD risk table).
- Rotate the BharatCode key: it was pasted into the Claude chat on 2026-10-26.

## Done
- 2026-10-26 Product renamed from RTI Saathi to UnSeal (package `unseal`).
- 2026-10-26 `rules/data/rti_act.json` (13 statute rules) + `central.json` (6 rules), every
  quote verified verbatim against the primary source; loader `rules/engine.py` (100% covered).
- 2026-10-26 `config.py` + `llm/client.py`: stateless strict Responses calls, 503 backoff 2/4/8 s,
  one doubled-budget truncation retry, one schema retry, request-id-only logs; 17 tests over a
  fake transport plus an opt-in live smoke test. BharatCode behaviour not yet seen live.
- 2026-10-26 Draft schemas (`llm/schemas.py`: Rewrite, Intake, Compose, AppealFacts), v1 prompts
  (`src/unseal/prompts/`), `client.structured_call` (retry stats), and the eval: 20 cases,
  checks A2 to A4, gates, results sheet, recordings; live runner opt-in.

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
- Transfer clock (S. 6(3)): the Act is silent; DoPT Guide says 30 days from the new authority's
  receipt. Engine default until decided: first-appeal clock on the original receipt.
- Not modelled yet: S. 7(3)(a) (fee-intimation time excluded) and S. 7(6) (free information
  after a missed deadline; relevant to the "fee wrongly demanded" appeal ground).
- Supreme Court orders on W.P.(C) 177/2026 not opened (captcha); "no stay" and "larger bench"
  are unverified. Recheck `personal_information` when the next listing appears.
- Rules sign-off: UNASSIGNED (skill `rti-rules-research`).

## Key decisions
- 2026-10-26 Name: UnSeal; Python package `unseal`; footer "Prepared with UnSeal. Not legal advice."
- 2026-10-26 ADR 0001: statute rules once in `rti_act.json`; jurisdiction files hold only their own rules.
