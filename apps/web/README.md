# UnSeal web app

Next.js (App Router) + TypeScript (strict) + Tailwind. Talks only to the UnSeal API
(`docs/api.md` at the repo root).

## Setup

```bash
npm install
cp .env.example .env.local   # API_ORIGIN: where /api/* is forwarded (default http://localhost:8000)
npm run dev                  # http://localhost:3000, redirects to /en, /hi or /ta
```

Run the API on port 8000 next to it; the browser never calls it directly.

## How the browser reaches the API (deploy)

The browser calls `/api/*` on the web app's own origin, and Next.js forwards each request to
`API_ORIGIN` (a rewrite in `next.config.ts`). The API's `unseal_session` cookie (HttpOnly,
SameSite=Lax) is therefore set on the web app's host: it stays first-party wherever the API
runs, so it works when the web app is on Vercel and the API is elsewhere.

When you deploy:

- **Web app:** set `API_ORIGIN` to the API's origin, for example `https://api.unseal.example`,
  **at build time** (rewrites are fixed when the app is built; on Vercel, set it in the project's
  environment variables). It is server-side only and not secret. Leave `NEXT_PUBLIC_API_URL`
  unset: setting it makes the browser call the API directly and the cookie becomes third-party.
- **API:** set `APP_BASE_URL` to the web app's public origin, exactly as the browser shows it,
  for example `https://unseal.example` (scheme and host, no path, no trailing slash). The
  browser's `Origin` header is forwarded through the proxy unchanged, and the API rejects writes
  whose `Origin` differs (`403 bad_origin`, ADR 0003). Its CORS setting does not matter for the
  web app any more, because the browser only ever makes same-origin requests.
- **Limits** (`next.config.ts`): the proxy allows 180 s per request (reading a reply letter calls
  the model) and request bodies up to 11 MB (reply uploads are at most 10 MB plus the form
  framing). These apply to a self-hosted `next start`. On a managed host, check that its own
  rewrite timeout and body limits are at least as high.

## Scripts

| Script | What it does |
| --- | --- |
| `npm run lint` | ESLint (Next rules plus the full jsx-a11y recommended set) |
| `npm run build` | Production build and type check |
| `npm test` | Vitest and React Testing Library unit tests |
| `npm run test:coverage` | Unit tests with a coverage report |
| `npm run test:e2e` | Playwright: builds and starts the app with `/api` mocked by `page.route`, runs axe on every page, saves screenshots in `e2e/screenshots/`, and checks the `/api` rewrite against a small echo server (`e2e/support/fake-upstream.mjs`). Run `npx playwright install chromium` once. |

## Layout

- `app/[lang]/`: every page, under `/en`, `/hi` or `/ta` (`proxy.ts` redirects a bare path).
- `lib/api.ts`: the typed API client and error mapping; `lib/schemas.ts` checks responses.
- `lib/intake-transcript.ts`: the intake conversation, kept in the browser and sent whole.
- `lib/appeal.ts`: when the first appeal is open and which grounds apply.
- `messages/{en,hi,ta}.ts`: all UI strings. The Hindi and Tamil files need native review.
- `components/flow/`: the new-case flow; `components/case/`: dashboard, case timeline, receipt
  date, reply reader and first appeal.
- `lib/samples.ts`: the three fictional sample cases (no API calls).

Prepared with UnSeal. Not legal advice.
