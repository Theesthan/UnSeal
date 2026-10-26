# Tamil and Hindi eval plan (day 1 spike)

**Question:** can `qwen-3.8-27b` understand and write Tamil and Hindi well enough for UnSeal to work natively in those languages, or do we take the PRD fallback (compose in English, translate, show both for the user to review)?
**Timebox:** 3 hours from first call. No verdict by then means we take the fallback.
**Output:** scored results sheets (`docs/eval/language-eval-results-ta.md`, `-hi.md`) and ADR `docs/adr/0002-language-strategy.md` recording the decision.

## What is tested

Only the language steps of the harness, with fictional applicants. Dates, fees and sections are never asked of the model; the eval also checks it does not invent them.

| Kind | Cases | What good looks like |
| --- | --- | --- |
| Rewrite | 1 to 4 | A "why" or opinion ask becomes a request for specific records; a third-party personal ask is flagged, not rewritten |
| Intake | 5 to 7 | Slots extracted from free text written in the language; a vague message gets one or two follow-up questions in the same language |
| Compose | 8, 9 | Formal subject line and questions, placeholders such as `<REG_NO>` kept verbatim |
| Appeal facts | 10 | One facts paragraph that uses only the dates it was given |

## Cases

Inputs were drafted by Claude. **A native speaker proofreads them before the run**: a typo in the input muddies the result.

### Tamil

| # | Kind | Input | Expected |
| --- | --- | --- | --- |
| TA-1 | Rewrite | எனது பருவத் தேர்வில் கணிதப் பாடத்தில் ஏன் இவ்வளவு குறைந்த மதிப்பெண் வழங்கப்பட்டது? | Certified copy of the evaluated answer script (subject, `<REG_NO>`, exam session); marks per question |
| TA-2 | Rewrite | எங்கள் வார்டில் உள்ள சாலை ஏன் இரண்டு வருடங்களாகப் போடப்படவில்லை? | Work order, sanctioned amount, tender and contractor, measurement book, completion certificate, with dates |
| TA-3 | Rewrite | எனது ஓய்வூதிய விண்ணப்பத்தை நிராகரித்தது சரியா என்று அதிகாரி விளக்க வேண்டும். | Copy of the rejection order, file notings, rules or circulars relied on |
| TA-4 | Rewrite | எனது பக்கத்து வீட்டுக்காரரின் வருமான வரி விவரங்களை வழங்கவும். | Personal-information flag; no request for that person's data; an aggregate alternative at most |
| TA-5 | Intake | நான் சென்னையில் உள்ள ஒரு அரசு கலைக் கல்லூரியில் படிக்கிறேன். ஏப்ரல் 2026 பருவத் தேர்வில் கணிதப் பாடத்தில் தோல்வி என்று முடிவு வந்தது. என் விடைத்தாளின் நகல் வேண்டும். தபாலில் அனுப்பினால் போதும். | Tamil Nadu; state university exams; April 2026 session; answer script copy; delivery by post; BPL unknown, so asked |
| TA-6 | Intake | 2025 ஜனவரியில் புதிய குடும்ப அட்டைக்கு விண்ணப்பித்தேன். இன்னும் கிடைக்கவில்லை. நான் வறுமைக் கோட்டுக்குக் கீழ் உள்ளவன்; என்னிடம் சான்று உள்ளது. | Tamil Nadu; civil supplies; application status and file notings since Jan 2025; BPL yes |
| TA-7 | Intake | அரசு அலுவலகத்தில் என் கோப்பு நகரவே இல்லை. | No draft; one or two follow-up questions in Tamil (which office, which application, when) |
| TA-8 | Compose | Accepted records (English): certified copy of the evaluated answer script, Mathematics, April 2026 session, `<REG_NO>`; marks per question; dates of evaluation and any revaluation | Tamil subject line and 3 questions, formal register, `<REG_NO>` intact |
| TA-9 | Compose | Accepted records (English): work order, sanctioned amount, completion certificate and measurement book entries for the road in `<WARD>` | Tamil subject line and 4 questions, `<WARD>` intact |
| TA-10 | Appeal facts | Filed by post 2026-08-03; received 2026-08-07; reply due 2026-09-06; no reply as of 2026-10-20. Ground (from code): no reply in time | One Tamil paragraph using exactly these dates; no section numbers, fees or new dates |

### Hindi

| # | Kind | Input | Expected |
| --- | --- | --- | --- |
| HI-1 | Rewrite | मेरा पासपोर्ट अब तक जारी क्यों नहीं हुआ? | Application status, police verification dates, file notings |
| HI-2 | Rewrite | CBSE ने 12वीं की भौतिकी परीक्षा में मुझे इतने कम अंक क्यों दिए? | Certified copy of the evaluated answer book (`<ROLL_NO>`, subject, year); marks per question |
| HI-3 | Rewrite | क्या रेलवे द्वारा मेरी नियुक्ति रद्द करना उचित था? | Copy of the cancellation order, file notings, rules relied on |
| HI-4 | Rewrite | मेरे पड़ोसी की आयकर रिटर्न की प्रति दीजिए। | Personal-information flag; no request for that person's data |
| HI-5 | Intake | मैं दिल्ली में रहता हूँ। मार्च 2026 में मैंने EPFO में PF निकासी का दावा किया था, लेकिन अब तक पैसा नहीं आया। मुझे दावे की स्थिति और फ़ाइल नोटिंग चाहिए। जवाब ईमेल से भेजें। | Central (EPFO); March 2026; claim status and file notings; delivery by email; BPL unknown, so asked |
| HI-6 | Intake | मेरे पिताजी की पेंशन जनवरी 2026 से बंद है। हमारे पास BPL कार्ड है। | Authority unclear, so asked (central or state pension); BPL yes |
| HI-7 | Intake | सरकारी दफ़्तर में मेरी फ़ाइल आगे नहीं बढ़ रही। | No draft; one or two follow-up questions in Hindi |
| HI-8 | Compose | Accepted records (English): status of PF withdrawal claim `<CLAIM_NO>` filed March 2026; file notings; name and designation of the officer holding it | Hindi subject line and 3 questions, `<CLAIM_NO>` intact |
| HI-9 | Compose | Accepted records (English): certified copy of the evaluated answer book, `<SUBJECT>`, `<ROLL_NO>`, May 2026 examination; marks per question | Hindi subject line and 2 questions, placeholders intact |
| HI-10 | Appeal facts | Same facts as TA-10 | One Hindi paragraph using exactly these dates; no section numbers, fees or new dates |

## Scoring

**Automated** (every call, all runs):

| Check | Rule |
| --- | --- |
| A1 Schema | Output parses against its Pydantic schema; count first-call passes and passes after one retry. Busy calls are excluded and reported (they say nothing about the model) |
| A2 No invented legal values | Every number in the output (Tamil and Devanagari digits included) must appear in the input; 2005, the year in the Act's name, is allowed and list numbering is ignored. A section word (`Section`, `S.`, `பிரிவு`, `धारा`) counts only when a number follows, since பிரிவு and धारा are also everyday words; a currency mark (`Rs`, `rupees`, `₹`, `ரூ.`, `ரூபாய்`, `रु.`, `रुपये`) always counts |
| A3 Placeholders | Every `<PLACEHOLDER>` in the input appears verbatim in the output |
| A4 Script | At least 80% of letters in user-facing fields (`USER_FACING` on each schema) are in the target script, excluding placeholders and acronyms such as CBSE, EPFO, PF. Reported, not gated: it feeds the reviewer's L score |

**Task (T)**, pass or fail per case against the Expected column. Any reviewer can score this.

**Language (L)**, 0 to 2 each, by a native speaker, one run per case:
- L1 Fluency: grammatical and natural.
- L2 Register: formal enough for a letter to a PIO; Hindi not Hinglish, Tamil not colloquial.
- L3 Terms: RTI terms correct. Reviewer's reference: பொதுத் தகவல் அலுவலர், தகவல் அறியும் உரிமைச் சட்டம், 2005; लोक सूचना अधिकारी, सूचना का अधिकार अधिनियम, 2005.

## Pass bar (proposal: agree it before the first call)

The PRD sets no bar, so this is a proposal. Per language:

| Gate | Bar |
| --- | --- |
| A1 | At least 9 of 10 first-call valid; 10 of 10 after one retry |
| A2 | Zero invented legal values. Any hit adds a code guard whatever the language decision |
| A3 | 10 of 10 |
| T | At least 8 of 10 |
| L | Mean of L1 to L3 at least 1.5, and no case scores 0 on L3 |

**Decision per language:**
- **Native:** every gate passes. Compose in the language.
- **Fallback:** A1, A3 and T pass but L fails. Compose in English, translate, show both side by side for the user to accept; fixed legal phrases come from templates, not the model.
- **Confirm-back intake:** intake cases (5 to 7) fail T. Keep intake in the language, but read every extracted slot back to the user from templates and require a confirm before drafting.
- If the fallback path is chosen, rerun cases 8 to 10 as translate-from-English to check the translation clears the L bar.

## How it runs

Everything below runs from `apps/api`. The pieces: draft schemas in `llm/schemas.py`, v1 prompts in `src/unseal/prompts/`, the cases in `tests/golden/lang_eval/cases.json` (the machine copy of the tables above), checks and gates in `src/unseal/evals/lang_eval.py`.

1. **Key:** put `BHARATCODE_API_KEY` in the repo-root `.env` only; never paste it into chat.
2. **Smoke call:** `uv run pytest -m live tests/live` makes one English rewrite, confirming the base URL, model name and structured output before spending the timebox.
3. **Run:** `uv run pytest -m live tests/golden/lang_eval` runs every case 3 times (sampling varies), sequentially, with a 4,096-token budget and `reasoning={"effort": "none"}` on intake. Add `-k tamil` or `-k hindi` for one language, or `LANG_EVAL_RUNS=1` for a quick pass. Roughly 20 cases x 3 runs x 1.5k tokens is near 90k tokens, around 1% of the 10M daily cap.
4. **Record:** every run is saved to `tests/fixtures/recorded/lang_eval/<case>.json` (fictional cases, so safe to commit); an offline test keeps those files valid against the schemas, and they double as fixtures for the harness tests.
5. **Score:** the run writes `docs/eval/language-eval-results-<ta|hi>.md` with the gates, a row per case (first-call valid, invented values, placeholders, script share) and every output, plus blank T and L1 to L3 columns for the reviewers. The test fails if an automated gate fails. Each rerun overwrites the sheet, so copy reviewer scores out first.
6. **Decide:** write ADR 0002 with the scores, the decision per language, and what would reopen it (a model change, or golden cases failing).

## Owners

- Tamil review: needs a native speaker (you, if you read Tamil).
- Hindi review: TBD (PRD open question on the team split).
