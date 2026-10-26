# UnSeal: Product Requirements

Oct 26, 2026 · @Theesthan

UnSeal turns a citizen's question into a filing-ready RTI application in English, Hindi or Tamil, tracks every statutory deadline, and drafts the first and second appeals. It is our BharatCode Build League entry, built on BharatCode's `qwen-3.8-27b` model, with submissions closing **Nov 10, 2026 at 11:59 PM IST**.

## Problem and opportunity

RTI requests often stall on avoidable mistakes, not on the law: the wrong framing, the wrong authority, and missed follow-up windows. UnSeal removes those three failure points in one guided flow.

- **Wrong framing.** The Act gives access to records an authority already holds. It does not oblige officers to give opinions or reasons, so "why" questions invite refusal. Applicants also over-explain, though Section 6(2) says no reason is needed.
- **Wrong place or format.** Central authorities follow the RTI Rules, 2012; each state sets its own fee and payment rules, and payment modes differ even between authorities in one state.
- **Lost follow-up.** A PIO who misses the deadline is a deemed refusal under Section 7(2), but the first appeal has its own 30-day window that applicants often miss.
- **Language.** Section 6(1) allows English, Hindi or the official language of the area, yet most guides and templates are English-only.

**The hackathon gap:** of 37 entries on the Build League page on 26 Oct 2026, 16 are coding tools and 7 are education or interview-prep tools. None mention RTI or Tamil. The leading entry had 14 website votes and every repo had 0 stars, so a clear civic tool with a strong demo can lead the community score.

## Goals, non-goals and success metrics

By 10 Nov, a first-time user gets a filing-ready application in under 5 minutes, and the app carries that case through to a drafted first appeal.

### Goals

1. Turn a free-text concern into record-specific RTI questions that pass a rules check.
2. Produce a correctly formatted application PDF in English, Hindi or Tamil.
3. Compute every statutory deadline in code, and remind the user before each one.
4. Draft the first and second appeals from the case history, including from a photo of the PIO's reply.

### Non-goals for v1

- Filing on the user's behalf or automating government portals; users file on rtionline.gov.in, by post or in person.
- Taking payments or storing BPL certificates and ID documents.
- Legal advice; every output carries a "not legal advice" footer.
- States other than Tamil Nadu, and WhatsApp (Cloud API setup and template approval add lead time; a Telegram bot needs only a BotFather token).

### Success metrics

| Metric | Target by 10 Nov |
| --- | --- |
| First message to downloadable PDF | Under 5 minutes |
| Golden-set questions passing the validator after rewrite | At least 27 of 30 |
| Deadline unit tests, incl. 35-day, 40-day and 48-hour cases | 100% passing |
| GitHub stars | 50 or more |
| BharatCode website votes | 40 or more (leader had 14 on 26 Oct) |

## Users and core journeys

Three personas set the v1 scope; the student asking for an answer sheet is the hero demo, because every voter recognises that problem.

| Persona | Need | Typical request |
| --- | --- | --- |
| Student | Copy of own evaluated answer sheet after a disputed result | State university exam cell (Tamil Nadu) or CBSE (central) |
| Citizen | Records behind a civic problem | Work orders, sanctioned amounts and completion certificates for a ward road |
| Repeat filer (activist, journalist) | Track many requests and appeals | One dashboard of open cases and due dates |

The answer-sheet case rests on *CBSE v. Aditya Bandopadhyay* (2011), where the Supreme Court held that evaluated answer books are "information" under the Act.

### Journey, end to end

1. **Describe.** The user explains the problem in English, Hindi or Tamil; UnSeal asks at most 5 follow-ups (authority, time period, records wanted, delivery mode, BPL status).
2. **Rewrite.** Each "why" or opinion question becomes a request for specific records (copies, file notings, dates, amounts); the user accepts or edits each change.
3. **Check.** The validator flags risky asks, such as third-party personal information under the amended Section 8(1)(j), before export.
4. **Export.** An application PDF plus a filing checklist: where to send it, fee, accepted payment modes, and what to keep as proof.
5. **Track.** The user logs the filing date and mode; reminders fire before the reply is due.
6. **Appeal.** On no reply, or a poor reply (typed in or photographed), UnSeal drafts the first appeal; after the appellate authority's window, the second appeal.

## Functional requirements

Eight P0 requirements make the demo work end to end; the five P1s are what make it stand out, so start them only once every P0 passes.

| ID | Requirement | Priority | Done when |
| --- | --- | --- | --- |
| FR-1 | Guided intake on web and Telegram, in English, Hindi and Tamil | P0 | A case reaches "ready to draft" in 5 follow-up questions or fewer |
| FR-2 | Question rewriter with accept or edit per question | P0 | Every "why" question in the golden set becomes a records request |
| FR-3 | Validator: personal-information asks, opinion asks, 500-word guidance, missing fields | P0 | Flags show before export; only missing mandatory fields block it |
| FR-4 | Authority routing (central or Tamil Nadu) with a confirmed PIO address | P0 | The user confirms authority and address before the PDF is made |
| FR-5 | Application PDF with correct Tamil and Hindi text shaping | P0 | Golden PDFs pass a visual check in all three languages |
| FR-6 | Rules engine for deadlines and fees, from versioned JSON | P0 | Unit tests cover the 30-, 35- and 40-day and 48-hour paths |
| FR-7 | Case tracker with a status timeline | P0 | Status runs draft, filed, reply due, replied or deemed refused, appealed, closed |
| FR-8 | Delete my data; export my case | P0 | One action removes every row and file for that user |
| FR-9 | Reminders on Telegram and web: 7 days before, 1 day before, on the due date | P1 | Each reminder is sent exactly once |
| FR-10 | First appeal drafter, Section 19(1) | P1 | The draft cites the case's dates and the grounds the user picked |
| FR-11 | Reply reader: photo of the PIO's reply to structured points | P1 | Reply date and per-question status extracted correctly on 5 sample letters |
| FR-12 | Second appeal drafter, Section 19(3) | P1 | Central cases follow the CIC format under Rule 8 |
| FR-13 | Sample-case gallery with fictional applicants | P1 | Voters can try 3 flows without typing personal data |

**Later (P2):** a WhatsApp channel, rules for more states, and voice input through a separate speech-to-text service, since the BharatCode API does not accept audio.

## How it works

A message enters through the web app or the Telegram bot. The API runs the harness, calls BharatCode only for language steps, and takes every date and fee from the rules engine before it builds the PDF.

### AI harness

The model handles language; code owns dates, fees and legal grounds. Every model call returns JSON checked against a Pydantic schema, and a failed check retries once, then asks the user.

**Pipeline** (one Responses call per step, `store: false`, history replayed each turn because the API is stateless):

1. **Intake** fills slots through function tools and stops when the slot set is complete.
2. **Classify** sets jurisdiction (central, Tamil Nadu, other), authority type, and the life-or-liberty flag, which the user must confirm.
3. **Rewrite** returns, per question: original text, rewritten text, records requested, and a one-line reason for the change.
4. **Validate** runs code checks first (word count, required fields), then a model check for personal-information and opinion asks; each flag has a severity.
5. **Compose** fills a Jinja template; the model writes only the subject line and the numbered questions.
6. **Read reply** takes a photo of the PIO's letter (image input) and returns the reply date and, per question, given, refused, partial or transferred, with any section cited.
7. **Draft appeal** picks grounds from a fixed list in code (no reply in time, incomplete reply, exemption wrongly applied, fee wrongly demanded); the model writes only the facts paragraph.

**Function tools** (BharatCode returns the call; our server runs it):

| Tool | Returns |
| --- | --- |
| `get_rules(jurisdiction)` | Fee, payment modes, languages, filing channels |
| `compute_deadlines(filed_on, received_on, via_apio, third_party, life_liberty)` | Every due date, each marked exact or estimated |
| `lookup_authority(query, jurisdiction)` | Candidates from our curated authority list |
| `save_case(fields)` | Case id |

**Model settings:**

- `qwen-3.8-27b`, available on the student plan with 10M tokens a day; `deepseek-v4.1-flash` needs Pro, so nothing depends on it.
- Structured output through `text.format` with a JSON schema; `reasoning: {effort: "none"}` on short extraction steps.
- `status: incomplete` or `finish_reason: length` counts as failure: keep the partial text, never run a partial tool call, and raise `max_output_tokens` once (the cap is 32,000, reasoning included).
- A 503 means busy: retry after 2, 4 and 8 seconds, then show a "busy, try again" state.
- Prompts live in `prompts/` with a version header; the golden-set eval must pass before a prompt change merges.

### RTI rules engine

All dates and fees come from `rules/data/*.json` (the statute once in `rti_act.json`, each jurisdiction's own rules in `central.json` and `tamil_nadu.json`; ADR 0001), versioned and unit-tested; the model never computes them. Values below were checked against the sources listed at the end on 26 Oct 2026.

| Rule | Value | Basis |
| --- | --- | --- |
| PIO reply | 30 days from receipt | Section 7(1) |
| Filed through an Assistant PIO | 35 days (5 days added to the 30) | Section 5(2), proviso |
| Third party involved | 40 days (to decide on disclosure and notify the third party) | Section 11(3) |
| Life or liberty at stake | 48 hours | Section 7(1), proviso |
| Transferred to another authority | Transfer within 5 days. The Act is silent on when the new PIO's period runs; the DoPT Guide (2013) says 30 days from its receipt. Until decided, the user's first-appeal clock stays on the original receipt | Section 6(3), proviso; DoPT Guide 2013 |
| No reply in time | Deemed refusal | Section 7(2) |
| First appeal | Within 30 days of the reply or of its due date; a late appeal is at the appellate authority's discretion | Section 19(1) |
| Appellate authority's decision | 30 days, extendable to 45 | Section 19(6) |
| Second appeal | Within 90 days of the decision, or of the appellate authority's deadline passing; a late appeal may be admitted for sufficient cause | Section 19(3) and proviso |
| Fee, central | Rs 10; Rs 2 per page of copies on A3 or smaller paper (larger paper at actual cost) | RTI Rules 2012 (G.S.R. 603(E)), Rules 3 and 4 |
| Fee, Tamil Nadu | Rs 10 | TN RTI (Fees) Rules 2005, per TNSIC |
| BPL applicants | No fee; central applications attach a copy of the BPL certificate | Section 7(5), proviso; RTI Rules 2012, Rule 5 |
| Payment modes, central (default) | Cash against receipt, demand draft, banker's cheque, Indian Postal Order, or electronic where the authority has it | RTI Rules 2012, Rule 6 |
| Length, central | Ordinarily 500 words or fewer; never rejected for length alone | RTI Rules 2012, Rule 3 |
| Personal information | Exempt as a class since 13 Nov 2025; under Supreme Court challenge (Venkatesh Nayak v. Union of India, W.P.(C) 177/2026 and connected matters) | Section 8(1)(j) as amended by DPDP Act Section 44(3); G.S.R. 843(E) |
| Language | English, Hindi or the official language of the area | Section 6(1) |

**Engine rules:**

- Count calendar days from the date of receipt. When only the posting date is known, add a configurable transit buffer (default 7 days) and label the date "estimated".
- Store accepted payment modes per authority, not per state; Tamil Nadu authorities differ (cash, postal order, demand draft, court fee stamp).
- Every rule carries `source_url` and `checked_on`; a rule older than 180 days shows a "recheck" warning in the UI.
- Flag the personal-information rule `under_challenge`, so the validator text can change if the Supreme Court rules on it.

## Tech stack and data model

The backend is Python because Tamil and Hindi PDFs need real text shaping: WeasyPrint shapes text through Pango and HarfBuzz. Test any alternative PDF library against the golden PDFs before switching. Repo layout and commands live in `CLAUDE.md`.

| Layer | Choice | Why |
| --- | --- | --- |
| Web | Next.js (App Router), TypeScript, Tailwind | Fast UI work; deploys on Vercel |
| API | FastAPI on Python 3.12, Pydantic v2 | One schema language for HTTP bodies and model outputs |
| Model client | `openai` Python SDK with `base_url` set to BharatCode | The API is OpenAI-compatible |
| Telegram bot | python-telegram-bot in webhook mode, inside the API service | One deploy for API and bot |
| PDF | WeasyPrint, Jinja2 templates, Noto Sans, Noto Sans Tamil, Noto Sans Devanagari | Correct conjuncts in Tamil and Hindi |
| Reminders | APScheduler job every 15 minutes over due deadlines | No extra infrastructure |
| Database | SQLite locally, Postgres in production; SQLAlchemy 2 and Alembic | Same models in both places |
| Hosting | Web on Vercel; API as a Docker image on any container host | WeasyPrint needs Pango system libraries |

### Data model

| Table | Key fields |
| --- | --- |
| `users` | id, channel (web or telegram), telegram_chat_id (encrypted), language, created_at |
| `applicants` | id, user_id, name, address, phone, all encrypted at field level |
| `cases` | id, user_id, applicant_id, jurisdiction, authority_name, pio_address, status, via_apio, third_party, life_liberty, filing_mode, filed_on, received_on |
| `questions` | id, case_id, original_text, rewritten_text, accepted, flags |
| `deadlines` | id, case_id, kind (pio_reply, first_appeal, faa_decision, second_appeal), due_on, estimated, notified_at |
| `documents` | id, case_id, kind (application, first_appeal, second_appeal, reply_image), storage_key, created_at |

Reply PDFs are converted to page images before the model sees them, because the API takes image input but not file input.

## Privacy, security and legal guardrails

The app holds names, addresses and personal grievances, so it stores the minimum, encrypts what it keeps, and lets users delete everything.

- **Secrets.** `BHARATCODE_API_KEY`, `TELEGRAM_BOT_TOKEN` and the field-encryption key live only in server environment variables. `.env` is git-ignored; only `.env.example` with placeholder values is committed. The submission form itself forbids secrets, tokens, private links and private user data.
- **Keys stay server-side.** The browser and the bot never see the BharatCode key; the web app calls our API, which calls BharatCode.
- **Personal data.** Applicant fields are encrypted at rest. Nothing personal goes in URLs, logs or analytics; logs redact phone numbers, emails and 12-digit ID-like numbers.
- **Data minimisation in model calls.** Each step gets only what it needs: the rewriter sees the questions, never the applicant's address. Every call uses `store: false`.
- **Retention and deletion.** Users can delete a case or their whole account at any time; closed cases are deleted automatically after 180 days.
- **Notice and consent.** A plain-language notice at the start says what is stored, why, and how to delete it, in line with DPDP Act principles.
- **No official look.** Documents never use government emblems or claim official status; every page carries "Prepared with UnSeal. Not legal advice."
- **Misuse.** Rate-limit per user, and refuse requests aimed at a named private individual; the amended Section 8(1)(j) exempts such information anyway.
- **Demo data.** The public demo and sample gallery use fictional applicants only.

## Build plan to 10 Nov

Days 1 and 2 settle the language fallback and the rules JSON, because everything else builds on them. After 3 Nov the work is P1 features, polish and the push for votes, so a slip there costs features, not the entry.

## Demo and launch plan

Submit the working MVP on **3 Nov** rather than on deadline day: stars and website votes only start once the repo is listed, and we keep pushing to the same repo afterwards. Each registered account gets one vote and can change it while voting is open.

### 90-second demo script

1. On Telegram, in Tamil: "My semester result looks wrong; I want to see my answer sheet."
2. UnSeal asks 3 questions, then rewrites the ask into a request for a certified copy of the evaluated answer script for that subject, register number and exam session.
3. The PDF arrives with correct Tamil rendering, plus a checklist: where to send it, Rs 10 fee, accepted payment modes.
4. Jump ahead: the user photographs a refusal letter; UnSeal reads it and drafts the first appeal with its due date.
5. The web dashboard shows the case timeline with every deadline.

### Launch checklist

- [ ] `BharatCode.txt` in the repo root; repo public; main repository link submitted
- [ ] README: one-line pitch, 30-second GIF, "Try it" links (web and Telegram), architecture picture, setup steps
- [ ] Repo description, topics and an MIT license set
- [ ] Demo video, 2 minutes or less, linked from the README
- [ ] Sample gallery live, so voters can try it without typing personal data
- [ ] Share with the campus GitHub Club and classmates with both links: the repo to star and the Build League page to vote

## Risks and open questions

The biggest unknown is Tamil and Hindi quality from `qwen-3.8-27b`, so it is tested on day 1, before anything is built on it.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Weak Tamil or Hindi output | The main differentiator fails | Day-1 eval on 10 prompts per language; fallback: compose in English, translate, show both for review; keep fixed legal phrases in templates |
| Invalid JSON or truncated output | Broken flows | Schema check plus one retry; never run a partial tool call |
| A wrong rule or fee | A user files incorrectly | Rules in JSON with source and date; "confirm with the authority" line on every checklist; disclaimer on every page |
| Missing PIO addresses | The user cannot route the request | The user confirms or types the address; curated list for the 20 most-asked central and Tamil Nadu authorities |
| Daily token cap or 503s during voting traffic | The demo fails while people try it | Cache model output for sample cases; backoff; a visible "queued" state |
| The Supreme Court changes Section 8(1)(j) | Validator text goes stale | Rule flagged `under_challenge`; one JSON edit updates it |

### Open questions

- [ ] Team split: who owns the API, web, bot and PDFs?
- [ ] Final name: check that "UnSeal" is not already an app or trademark.
- [ ] What must `BharatCode.txt` contain? The page only says it must be in the repo root; ask the organisers.

## Sources

Primary sources, all opened and quoted on 26 Oct 2026; the verbatim quotes live in `apps/api/src/unseal/rules/data/*.json`.

- RTI Act 2005, DoPT consolidated text "as on 18 Nov 2025", already showing the DPDP amendment to s. 8(1)(j): https://rti.dopt.gov.in/Writereaddata/RTI%20Act,%202005%20(Amended)-English%20Version.PDF
- RTI Rules 2012, G.S.R. 603(E), 31 Jul 2012 (fee, 500 words, copy fee, BPL certificate, payment modes): https://www.niti.gov.in/sites/default/files/2025-07/RTI%20Rules%20Final%20PDF.pdf
- DPDP Act 2023, s. 44(3) (Gazette, 11 Aug 2023): https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf
- MeitY G.S.R. 843(E), 13 Nov 2025, bringing s. 44(3) into force: https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf
- Supreme Court cause list, 7 Aug 2026, item 31 (W.P.(C) 177/2026 and connected matters pending): https://api.sci.gov.in/jonew/cl/2026-08-07/M_J_1.pdf
- DoPT Guide on the RTI Act, OM 1/32/2013-IR (transfer clock; guidance, not statute): https://rti.dopt.gov.in/Writereaddata/Guide_2013-issue.pdf
- RTI Online portal (central authorities only): https://rtionline.gov.in/
- Still to source: BharatCode Build League rules and API docs; Tamil Nadu fee rules (TNSIC).
