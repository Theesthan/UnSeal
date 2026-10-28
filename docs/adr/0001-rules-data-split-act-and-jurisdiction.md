# 0001. Statute rules live once in rti_act.json; each jurisdiction file holds only its own rules

Date: 2026-10-26
Status: accepted

## Context
CLAUDE.md planned `rules/data/central.json` and `rules/data/tamil_nadu.json`. Most legal values (the 30, 35, 40-day and 48-hour reply periods, transfers, deemed refusal, appeal windows, the BPL exemption, Section 8(1)(j)) come from the RTI Act 2005 and are identical for every jurisdiction. Copying them into each file means two edits for every change, and the PRD promises that one JSON edit updates the Section 8(1)(j) rule if the Supreme Court rules on it.

## Decision
`rules/data/rti_act.json` holds the statute rules once. `rules/data/<jurisdiction>.json` holds only that jurisdiction's own rules: application fee, copy fee, word limit (central only), payment modes, filing channels. `load_rules(jurisdiction)` returns both as `Rules.act` and `Rules.local`. Every rule in both files carries `basis`, `source_url` (an official `.gov.in` or `.nic.in` host), `checked_on` and a verbatim `quote`.

## Alternatives considered
- Two self-contained files with the Act duplicated: rejected, two edits per statute change and silent drift.
- One file for everything with jurisdiction keys: rejected, harder to review per jurisdiction and mixes statute with state fee rules.

## Consequences
- A statute change, or the `under_challenge` flag, is one edit in `rti_act.json`.
- Adding a state is one new file, with no copy of the Act.
- Payment modes in a jurisdiction file are that jurisdiction's statutory default; per-authority modes (CLAUDE.md) layer on top when the authority list exists.
- Reopen if a state amends a statutory period for its own authorities, which the Act does not allow today.
