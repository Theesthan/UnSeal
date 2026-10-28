# UnSeal

UnSeal turns a citizen's concern into a filing-ready Right to Information (RTI) application in English, Hindi or Tamil, tracks every statutory deadline, and drafts the first and second appeals. It runs on the web and on Telegram, for central public authorities and Tamil Nadu.

Built for the BharatCode Build League on BharatCode's `qwen-3.8-27b` model.

> Prepared with UnSeal. Not legal advice. Every date, fee and section number comes from versioned rules data with its official source, never from the model.

## What it does

| Step | What happens | Who decides |
| --- | --- | --- |
| Intake | The user describes the problem in their own words; UnSeal asks a few follow-ups and suggests the public authority from a curated list | The model extracts facts; the user confirms the authority and PIO address |
| Questions | Each question is rewritten into a request for records ("why" becomes "certified copy of...") | The model rewrites; the user accepts or edits |
| Checks | Personal-information asks, opinion asks, the 500-word guidance (central), missing addresses | Code (`harness/validate.py`) |
| Application PDF | A letter with correct Tamil and Devanagari shaping, fee and payment mode | Template plus rules data |
| Tracking | Deadlines for the reply, first appeal, appellate decision and second appeal; reminders 7 days, 1 day and on the day | Code (`rules/deadlines.py`) |
| Reply reader | A photo or PDF of the PIO's reply is read into dates and per-question status (with consent; the photo is never stored) | The model reads; code checks the date and suggests grounds |
| Appeals | First appeal (S. 19(1)) and second appeal (S. 19(3)) in the CIC or TNSIC format | Template plus rules data; no model call |

## Repo

```
apps/api   Python 3.12, FastAPI, the AI harness, the Telegram bot, PDFs, rules data
apps/web   Next.js, TypeScript, Tailwind
docs       PRD, API contract, ADRs, evals
```

Start with [docs/PRD.md](docs/PRD.md), then [docs/api.md](docs/api.md) and [CLAUDE.md](CLAUDE.md).

## Run it locally

API (from `apps/api`, with [uv](https://docs.astral.sh/uv/)):

```bash
cp ../../.env.example ../../.env
```

Fill in the values in `.env` (never commit it), then:

```bash
uv sync
```

```bash
uv run alembic upgrade head
```

```bash
uv run uvicorn unseal.main:app --reload --port 8000
```

Web (from `apps/web`):

```bash
npm install
```

```bash
npm run dev
```

The web app runs on port 3000 and calls the API. PDF rendering needs Pango and HarfBuzz (WeasyPrint); on a machine without them, use the Docker image in `apps/api/Dockerfile`.

## Tests

From `apps/api`:

```bash
uv run pytest -q
```

PDF rendering tests, in Docker (from the repo root):

```bash
docker build -t unseal-api apps/api
```

```bash
docker run --rm unseal-api uv run pytest -q tests/pdf tests/unit/test_pdf_template.py tests/unit/test_pdf_appeal.py
```

Live tests against BharatCode are opt-in (`-m live`) and need `BHARATCODE_API_KEY` in `.env`.

## Privacy

Anonymous sessions (a random cookie, only its hash stored). Applicant details are encrypted at rest and never sent to the model; phone numbers and emails in typed text are masked before any model call. A photo of a reply letter goes to the model only after the user consents, with camera metadata stripped, and is never stored. One action deletes every row and file of a user; closed cases are deleted after 180 days.
