---
name: architecture-decision-records
description: Use when a decision constrains future UnSeal work (a dependency, a schema shape, a pattern, a rejected alternative, an override of CLAUDE.md or the PRD) or when someone asks why a past choice was made. Records it as a short ADR in docs/adr/.
---

# Architecture Decision Records

An ADR captures one decision: the context that forced it, the options weighed, what was chosen and why. A future contributor, or a future Claude session, gets the *why* without re-deriving it. The PRD says what we build; an ADR says why a technical choice beat its alternatives.

## When to write one (spot these yourself, do not wait to be asked)
- A new dependency or service is chosen or rejected.
- A schema shape is decided (a new table, an encrypted field, an identity rule).
- A pattern is set that other code will copy, or an existing one is deviated from.
- Something in CLAUDE.md or docs/PRD.md is overridden for a reason.
- A "we considered X but did Y" conversation happens: that sentence is the ADR.

Not every choice. A variable name is not an ADR. Test: would someone a month from now plausibly ask "why didn't they just...?" If yes, write it.

## UnSeal examples from the PRD
- **Tamil/Hindi fallback.** The day-1 eval of `qwen-3.8-27b` (10 prompts per language) decides whether Tamil and Hindi are composed natively or via "compose in English, translate, show both for review" with fixed legal phrases kept in templates. Context: the eval result. Decision: the path chosen. Reopen when: the model improves or golden cases start failing.
- **WeasyPrint over another PDF library.** WeasyPrint shapes Tamil and Devanagari through Pango and HarfBuzz. Adding or switching a library is an ADR whose context cites a run against the golden PDFs in en, hi and ta (the PRD requires that test first).
- **SQLite locally, Postgres in production.** Any change to that split (for example, keeping SQLite for the demo) is an ADR. Consequences must say how Alembic migrations and Fernet field encryption behave on both.
- Also ADR-worthy: adding a speech-to-text service for P2 voice input, or letting any model output feed something the rules engine owns.

## Format
One file: `docs/adr/NNNN-short-kebab-title.md`, next free number, indexed in `docs/adr/README.md`. Create `docs/adr/` with the first ADR if it does not exist.

```markdown
# NNNN. <Title: the decision as a statement>

Date: YYYY-MM-DD
Status: accepted | superseded by NNNN | deprecated

## Context
What forced a decision. The constraint, the failure, the requirement. 2-6 sentences.

## Decision
What we are doing. Present tense, concrete.

## Alternatives considered
- <Option>: why rejected (one line each; "rejected" beats "not chosen")

## Consequences
What gets easier, what gets harder, what we are now committed to.
Include the trigger that would reopen this decision.
```

## Rules
- **One decision per ADR.** Two decisions, two files.
- **Short.** Readable in two minutes. Depth links out to the PRD or a doc in `docs/`.
- **Never edit an accepted ADR's decision.** Supersede it with a new one and cross-link both. A reversal needs a superseding ADR, not a quiet code change. (Typo fixes and consequences learned later are fine; say so.)
- **Same PR as the change** that implements the decision. Use a Conventional Commit; `docs:` for an ADR-only change.
- **Index it:** add a one-line entry to `docs/adr/README.md`. The number is permanent; never renumber.
- **Scope changes go PRD first.** If the decision changes scope or a golden rule, update docs/PRD.md, then CLAUDE.md, then link the ADR from both.
- **The repo is public.** No secrets, tokens, private links or real personal data in an ADR. Refer to env vars by name only.

## Starting point
The PRD and CLAUDE.md already record decisions made before any code (stateless Responses calls with `store=False`, code owns dates, fees and legal grounds, the Telegram bot inside the API service, WeasyPrint). Do not back-fill them all. Write an ADR the first time one is challenged, reversed or extended.
