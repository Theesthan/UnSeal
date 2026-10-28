# 0002. Compose natively in Tamil and Hindi, with a fixed RTI glossary in every prompt

Date: 2026-10-27
Status: proposed (accept once a native speaker's T and L scores clear the bar in docs/language-eval-plan.md)

## Context
The PRD's biggest risk is weak Tamil or Hindi from `qwen-3.8-27b`. The day-1 eval (`docs/language-eval-plan.md`, 10 fictional cases per language) found v1 prompts structurally reliable (10 of 10 schema-valid on the first call, no invented legal values, placeholders kept) but wrong on legal and administrative terms: Tamil வேலைத்தட்டு for work order, சான்றிதழ் நகல் for certified copy; Hindi दिखाने-कहने का नोटिस for show-cause notice, जन-संस्था for public authority; and one Tamil explanation that inverted the law.

Prompt v2 added only a glossary block rendered per language from `src/unseal/llm/glossary.json`, where every term carries an official source and a confidence. Against the same glossary, term errors fell from 7 to 0 (Tamil) and 2 to 0 (Hindi), and missed terms from 13 to 1 and 4 to 1 (`docs/eval/prompt-versions.md`). All automated gates pass for both languages. One v2 run returned an empty rewrite that every gate accepted; output validators now reject that and the client retries.

## Decision
Compose user-facing text natively in Tamil and Hindi with prompt v2 (glossary included). Fixed legal phrases in documents (Act name, PIO, footer, labels) come from templates and the glossary, never from the model. The "compose in English, translate, show both" fallback stays available per language if the native review fails.

## Alternatives considered
- English first, translate, show both: rejected for now; doubles calls on a slow shared API and still needs the glossary for the translation.
- Template-only legal text with the model writing nothing in Tamil or Hindi: rejected; the rewrite and follow-up questions must be in the user's language.
- No glossary (v1): rejected; consistent term errors.

## Consequences
- Every prompt change re-runs the eval, including the term measures; a new term error is a regression.
- The glossary is now a reviewed artefact: three Tamil terms are low confidence (file notings, completion certificate, the field term for measurement book) and need a native check.
- Known v2 slips to address in v3 or by review: a garbled Hindi word (HI-3), a stray Tamil prefix on questions (TA-9), a Hindi typo (HI-8), and occasional truncation (raise the eval budget or shorten outputs).
- Reopen if: the native review fails the L bar for a language, the model changes, or golden cases start failing.
