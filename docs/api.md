# UnSeal API contract (v1)

The web app talks only to this API (`NEXT_PUBLIC_API_URL`); the Telegram bot calls the same service layer in-process. JSON everywhere except the PDF downloads. Generated OpenAPI lives at `/docs` once the API runs; this file is the contract the two are built against.

## Conventions
- **Identity (ADR 0003):** `POST /session` sets an `HttpOnly`, `Secure`, `SameSite=Lax` cookie `unseal_session`. Every other route needs it (`401 {"error": "no_session"}` without). Browsers send it with `credentials: "include"`.
- **Writes** (`POST`, `PUT`, `PATCH`, `DELETE`) must carry `Origin` equal to `APP_BASE_URL` (`403 {"error": "bad_origin"}`).
- **IDs** are opaque UUIDv4. Another user's case is `404 {"error": "not_found"}`, same as a missing one.
- **Languages:** `en`, `hi`, `ta`. **Jurisdictions:** `central`, `tamil_nadu`.
- **Errors:** `{"error": "<code>", "detail": ...}`. Codes the UI must handle:

| Status | `error` | Meaning in the UI |
| --- | --- | --- |
| 503 | `busy` | "Busy, try again" (BharatCode queue, timeout or 503) |
| 422 | `ask_user` | The model could not produce a usable answer twice: ask the user to rephrase |
| 422 | `incomplete` | The answer was cut off: offer a retry |
| 409 | `blocked` | Export blocked; `detail.flags` lists the blocking flags |
| 409 | `too_early` | Second appeal before the appellate authority's time ran out; `detail.earliest` is the first allowed day |
| 409 | `wrong_status` | The case's status does not allow this action yet (or any more) |
| 400 | `invalid_grounds` | An appeal ground that cannot apply (`no_reply` after a reply arrived) |
| 400 | `invalid_payment_mode` | Not a payment mode the jurisdiction's rules accept |
| 400 | `consent_required` | Reply upload without `consent=true` |
| 400 | `unreadable_file` | The upload is not a PDF or an image we can open |
| 400 | `too_many_pages` | A PDF with more than 4 pages |
| 411 | `length_required` | Upload without a `Content-Length` |
| 413 | `too_large` | Upload over 10 MB |
| 429 | `rate_limited` | Slow down |
| 400 | `invalid` | Request body failed validation; `detail` has field errors |

- **Dates** are ISO `YYYY-MM-DD` (India dates); timestamps are ISO UTC.

## Session and account
| Route | Body | Response |
| --- | --- | --- |
| `POST /session` | `{"language": "ta"}` | `204`, sets the cookie (a new anonymous user; idempotent if the cookie is valid) |
| `GET /me` | | `{"language": "ta", "cases": 2}` |
| `PATCH /me` | `{"language": "hi"}` | `204` |
| `DELETE /me` | | `204`; every row and stored file of the user is gone and the cookie is cleared (FR-8) |
| `GET /me/export` | | JSON download of all the user's cases, applicant details decrypted (FR-8) |

## Reference data
| Route | Response |
| --- | --- |
| `GET /rules/{jurisdiction}` | `{"application_fee": 10, "copy_fee_per_page": 2, "word_limit": 500 or null, "payment_modes": [...], "filing_channels": [...], "bpl_certificate_required": true, "sources": [{"rule": "...", "basis": "...", "source_url": "...", "checked_on": "...", "recheck": false}]}` |
| `POST /authorities/search` with `{"q": "cbse", "jurisdiction": "central" or null}` (in the body: search text never goes in a URL) | `[{"id": "...", "name": "...", "name_ta": ..., "name_hi": ..., "jurisdiction": "...", "pio_designation": "...", "pio_address": "...", "rti_online": true}]` |

## Cases
`Case` object:
```json
{
  "id": "uuid", "language": "ta", "jurisdiction": "tamil_nadu", "status": "draft",
  "authority_name": null, "pio_address": null, "has_applicant": false,
  "via_apio": false, "third_party": false, "life_liberty": false,
  "filing_mode": null, "filed_on": null, "received_on": null, "received_estimated": false,
  "reply_received_on": null, "appeal_filed_on": null, "faa_decision_received_on": null,
  "questions": [{"id": "uuid", "position": 1, "original_text": "...", "rewritten_text": "...",
                 "records_requested": ["..."], "reason": "...", "personal_information": false,
                 "suggestion": null, "accepted": false}],
  "deadlines": [{"kind": "pio_reply", "due_on": "2026-11-26", "due_at": null, "estimated": true}],
  "created_at": "2026-10-27T10:00:00Z"
}
```
Statuses: `draft`, `filed`, `reply_due`, `replied`, `deemed_refused`, `appealed`, `closed`.

| Route | Body | Response |
| --- | --- | --- |
| `POST /cases` | `{"language": "ta", "jurisdiction": "tamil_nadu"}` (jurisdiction optional until intake) | `201 Case` |
| `GET /cases` | | `[{"id", "status", "authority_name", "next_deadline": {"kind", "due_on", "due_at", "estimated"} or null, "created_at"}]` |
| `GET /cases/{id}` | | `Case` |
| `DELETE /cases/{id}` | | `204`; rows and files gone (FR-8) |
| `POST /cases/{id}/intake` | `{"message": "free text in en, hi or ta"}`. The server keeps no intake history: on each follow-up, send the whole conversation so far in `message` (the first description, then each follow-up question and the user's answer, one per line; 4000 characters at most). Nothing is stored until the user confirms an authority | `{"intake": {jurisdiction_hint, authority, time_period, records_wanted, delivery_mode, bpl, follow_up_questions, ready_to_draft}, "authorities": [candidates]}` (FR-1, FR-4) |
| `PUT /cases/{id}/authority` | `{"jurisdiction", "authority_name", "pio_address", "via_apio", "third_party", "life_liberty"}` | `Case` (the user confirms authority and address, FR-4) |
| `PUT /cases/{id}/applicant` | `{"name", "address", "phone": null, "bpl": false}` | `204` (stored encrypted; never echoed back except in `/me/export`) |
| `POST /cases/{id}/questions` | `{"text": "why ..."}` | `201 Question` (runs the rewrite step, FR-2) |
| `PATCH /cases/{id}/questions/{qid}` | `{"rewritten_text": "...", "accepted": true}` (either) | `Question` |
| `DELETE /cases/{id}/questions/{qid}` | | `204` |
| `GET /cases/{id}/validation` | | `{"flags": [{"code", "severity": "warn" or "block", "question": 0 or null, "basis", "under_challenge"}]}` (FR-3) |
| `POST /cases/{id}/application` | `{"payment_mode": "cash", "place": "Chennai"}` | `200 application/pdf` (FR-5), or `409 blocked` |
| `POST /cases/{id}/filing` | `{"filed_on": "2026-10-27", "filing_mode": "post", "received_on": null}` | `Case` with deadlines; status `reply_due` (FR-6, FR-7) |
| `PUT /cases/{id}/receipt` | `{"received_on": "2026-10-30"}` | `Case`; the actual receipt replaces the estimate and the PIO and first-appeal deadlines restart from it. Only while `reply_due`; a date before the filing is `400 invalid` |
| `POST /cases/{id}/reply/read` | multipart: `file` (photo or PDF of the PIO's reply, 10 MB and 4 pages at most), `consent=true` | `{"letter_date": "2026-09-01" or null, "items": [{"number": 1, "status": "given" or "refused" or "partial" or "transferred" or "unclear", "section_cited": "8(1)(j)" or null}], "fee_demanded": false, "transferred_to": null, "suggested_grounds": ["refused", "incomplete", "fee_demanded"]}` (FR-11). Nothing is stored; `letter_date` is null when unreadable or impossible, and it is the letter's date, not the day the user received it: ask, then `POST /reply`. Allowed while `reply_due`, `deemed_refused` or `replied` |
| `POST /cases/{id}/reply` | `{"received_on": "2026-11-20"}` | `Case`; status `replied`, `reply_received_on` set, first-appeal deadline from the reply |
| `POST /cases/{id}/appeal` | `{"grounds": ["no_reply", "incomplete", "refused", "fee_demanded"] (one or more, no repeats), "faa_address": "...", "details": "", "delay_reason": "", "place": ""}` | `200 application/pdf`, the first appeal under S. 19(1) (FR-10). No model call: dates, filing mode and grounds are template text. Allowed once replied or deemed refused (including a `reply_due` case past the PIO's day) and after `appealed` (re-download); else `409 wrong_status`. `409 blocked` without the PIO or applicant address; `400 invalid_grounds` |
| `POST /cases/{id}/appeal/filing` | `{"filed_on": "2026-11-25", "received_on": null}` | `Case`; status `appealed`, `appeal_filed_on` set, FAA decision (S. 19(6)) and second-appeal (S. 19(3)) deadlines |
| `POST /cases/{id}/appeal/decision` | `{"received_on": "2026-12-20"}` | `Case`; `faa_decision_received_on` set, and the second-appeal deadline now runs 90 days from it (S. 19(3)). Only while `appealed`; a date before the first appeal or in the future is `400 invalid` |
| `POST /cases/{id}/second-appeal` | `{"grounds": ["no_reply", "no_decision", "refused", "incomplete", "incorrect", "fee_demanded"] (one or more, no repeats), "faa_address": "...", "details": "", "hearing_mode": "virtual" or "direct" or null (Tamil Nadu form), "delay_reason": "", "place": ""}` | `200 application/pdf` (FR-12): the CIC rule 8 format for central cases, the TNSIC form for Tamil Nadu, with the copies to enclose. No model call. Only while `appealed`; with no recorded decision, `409 too_early` until the appellate authority's outer limit (S. 19(6)) has passed; `400 invalid_grounds` for `no_decision` after a decision or `no_reply` after a reply; `409 blocked` without the PIO or applicant address |
| `POST /cases/{id}/close` | | `Case`; status `closed` |

Flag codes (`validation`): `missing_pio_address`, `missing_applicant_address`, `no_questions` (block); `over_word_limit`, `personal_information`, `opinion_ask` (warn). The UI words them in the user's language.

## Telegram
`POST /telegram/webhook` with header `X-Telegram-Bot-Api-Secret-Token` equal to `TELEGRAM_WEBHOOK_SECRET`; anything else is `403`. It is outside the per-IP rate limit (every bot user arrives from Telegram's IPs); the bot limits model calls per chat.

## Health
`GET /health` returns `{"status": "ok"}` (no session needed).
