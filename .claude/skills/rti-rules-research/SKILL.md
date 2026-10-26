---
name: rti-rules-research
description: Use when adding or changing a rule in rules/data/*.json (a deadline, fee, payment mode, language rule or exemption), when a rule shows a "recheck" warning, or when someone asks whether an RTI rule still holds. Produces a cited, dated finding a human can verify, never an answer from memory or from the model.
---

# RTI Rules Research

**Read this first.** The output is a **finding for a human to verify**. It is not legal advice, and no
agent may mark a legal question closed. Until a named person signs off, the finding is provisional.

Two failure modes matter most:

1. **Writing a value nobody opened the source for.** A plausible section number, day count or fee
   from memory is worse than `OPEN`, because the next reader treats it as settled.
2. **Letting the model or a guess fill a legal value.** The model writes words; code decides dates,
   fees and legal grounds. Values enter only through `apps/api/src/unseal/rules/data/central.json`
   and `tamil_nadu.json`, read by `rules/engine.py`. Never put one in a prompt, template, test
   fixture or web component.

## When to run it

- Any edit to `rules/data/*.json`, or a new rule, jurisdiction or authority entry.
- A rule whose `checked_on` is older than 180 days (the UI shows "recheck").
- A user or judge asks "is this still the law?", or there is news of an amendment, notification,
  CIC or court order, or pending challenge.

## Source ladder (prefer the top)

1. The statute text: the RTI Act 2005, as amended.
2. Rules: the RTI Rules 2012 (central); the Tamil Nadu fee rules as published by TNSIC.
3. Gazette notifications.
4. Commission material: CIC orders and guidelines, TNSIC orders.
5. Court judgments (Supreme Court first).
6. Explainers and government help pages: **leads only**. Use them to find the primary source, then
   cite the primary. A blog or news item never stands as the only source for a value.

Payment modes belong to an **authority**, not a state. Source them from that authority or the state
rules, never from a state-wide generalisation.

## Procedure (one rule at a time)

1. **Name the rule.** Jurisdiction (`central` or `tamil_nadu`), kind (deadline, fee, payment mode,
   language, exemption) and, for payment modes, the authority.
2. **Open the source and quote the operative sentence.** Record the URL you actually opened. If you
   could not open it, the finding is `OPEN` and the JSON does not change.
3. **Check currency.** Look for later amendments, notifications, orders and pending challenges. A
   correct old text is not a current rule.
4. **Write the JSON.** Set the value, `source_url`, and `checked_on` (today's date, ISO, the day you
   opened the source). Bump `checked_on` only after reopening the source. Never refresh a date to
   silence the "recheck" warning.
5. **Set `under_challenge` honestly** (see below).
6. **Change the docs in the same change.** Update `docs/PRD.md` first (the rules table and the
   Sources list), then the RTI rules table in `CLAUDE.md`. The two must agree with the JSON.
7. **Test.** Add or adjust engine tests for every changed rule, then run from `apps/api`:
   `uv run pytest -q` and `uv run ruff check . --fix && uv run ruff format .`.
8. **Sweep for strays.** Search `apps/api/src`, `apps/api/prompts`, `apps/api/tests` and `apps/web`
   for the old and new numbers. A fee, deadline or section number outside `rules/data/*.json` is a bug.

```
WRONG  Authority: Section <N> gives <X> days.   (from memory; nobody opened the text)
RIGHT  Authority: OPEN. Section and period UNVERIFIED. Next: open the current text, quote the
       operative sentence, cite the section, then set checked_on.
```

## `under_challenge`

- Today the personal-information rule (S. 8(1)(j) as amended by DPDP Act s. 44(3)) carries the flag
  because a Supreme Court challenge is pending. Use the same flag for any other rule a primary
  source shows is under challenge, and note it in the PRD change.
- Set it when a primary source (court record, order, notification) shows a pending challenge. A
  news report alone is a lead: record it as a note and look for the primary.
- Clear it only when a primary source disposes of the challenge. Record the date, then update the
  validator text. Never clear it because the topic went quiet.
- While it is set, user-facing text must say the position may change.

## When sources disagree

1. **Record both.** Source A says X (quote, URL, date); source B says Y (quote, URL, date).
2. **Rank them.** A later or higher authority beats an earlier or lower one (statute over
   explainer, a binding judgment over a commission note). If you cannot tell which controls, mark
   the finding `DISPUTED`.
3. **Use the conservative value for the user**, the one least likely to cost them a right or money:
   the earlier date for a deadline they must meet, the stricter filing or payment requirement, and
   the cautious warning for a personal-information ask.
4. **Flag it.** Keep the "confirm with the authority" line on the checklist, put the dispute in
   the PR description, and ask a human to decide. If the JSON has no place for a note, ask before
   adding a field (that needs a PRD update).

## Output template

One block per rule. Copy it, fill every field, leave `OPEN` where it is open.

```
Rule:             <kind> (<jurisdiction>[, authority])
Value:            OPEN | <value as it will appear in the JSON>
Authority:        <instrument, section or rule number, quoted operative sentence>
source_url:       <URL you opened>
Source type:      statute | rules | gazette | commission | court | explainer (lead only)
Currency check:   <amendments, notifications, challenges looked for, and what was found>
Conflicts:        none | <A vs B, which value used, why>
under_challenge:  true | false (basis)
checked_on:       YYYY-MM-DD
Docs updated:     PRD table + Sources, CLAUDE.md table, tests
Sign-off:         <named human> | UNASSIGNED
```

The sign-off is a person, not a role. If you cannot name one, write `UNASSIGNED` and say so in the
summary, because an unassigned finding is an unowned one.

## Checklist

- [ ] Every value quoted from an opened primary source (explainers are leads only), or marked `OPEN`
- [ ] `source_url` and `checked_on` set on the JSON rule; no date bumped without reopening the source
- [ ] `under_challenge` set or cleared on a primary source
- [ ] Conflicts recorded with both sides, the conservative value used, and a human asked to decide
- [ ] PRD table and Sources, then the CLAUDE.md table, updated in the same change
- [ ] Engine tests cover the change; pytest and ruff pass
- [ ] No fee, deadline or section number added outside `rules/data/*.json`
- [ ] No model output or guess supplied any legal value
- [ ] Sign-off names a person, or says `UNASSIGNED`
