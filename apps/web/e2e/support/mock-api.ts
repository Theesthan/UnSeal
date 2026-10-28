// An in-memory stand-in for the UnSeal API (docs/api.md), installed with page.route on the web
// app's own /api path (the same-origin proxy the browser uses in production). It follows the
// contract's shapes, status rules and error codes; dates in it are fixed fictional values.
import type { Page, Route } from "@playwright/test";
import { AUTHORITY_ID, CASE_ID, FIXTURES, QUESTION_IDS, type Lang } from "./fixtures";

export const APP_ORIGIN = "http://localhost:3100";
export const API = `${APP_ORIGIN}/api`;

type Json = Record<string, unknown>;

export interface Flag {
  code: string;
  severity: "warn" | "block";
  question: number | null;
  basis: string | null;
  under_challenge: boolean;
}

export interface ApiCall {
  method: string;
  path: string;
  search: string;
  body: unknown;
  raw: string | null;
  origin: string | undefined;
}

export interface MockOptions {
  lang?: Lang;
  /** Route keys ("POST /cases/:id/intake") that answer 503 busy the first time. */
  busyOnce?: string[];
  /** Fixed validation flags; by default they are derived from the case like the real validator. */
  flags?: Flag[];
  /** Make POST /application answer 409 blocked with these flags. */
  applicationBlocked?: Flag[];
  /** A case that already exists (to resume a draft or open the timeline). */
  initialCase?: Json;
}

export interface MockApi {
  calls: ApiCall[];
  intakeMessages: string[];
  current(): Json | null;
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

export const RULES: Record<string, Json> = {
  tamil_nadu: {
    application_fee: 10,
    copy_fee_per_page: 2,
    word_limit: null,
    payment_modes: ["cash", "court_fee_stamp", "postal_money_order", "demand_draft", "bankers_cheque"],
    filing_channels: ["rti_online", "post", "in_person"],
    bpl_certificate_required: true,
    sources: [
      {
        rule: "application_fee",
        basis: "Tamil Nadu Right to Information (Fees) Rules, 2005, r. 3(a)",
        source_url: "https://www.tn.gov.in/rti/public/TN_RTI_Fees_Rules_2005.pdf",
        checked_on: "2026-10-27",
        recheck: false,
      },
    ],
  },
  central: {
    application_fee: 10,
    copy_fee_per_page: 2,
    word_limit: 500,
    payment_modes: ["cash", "demand_draft", "bankers_cheque", "indian_postal_order", "electronic"],
    filing_channels: ["rti_online", "post", "in_person"],
    bpl_certificate_required: true,
    sources: [],
  },
};

/** What the reply reader returns for the sample letter, per case language. */
export const READINGS: Record<Lang, Json> = {
  en: {
    letter_date: "2026-10-15",
    items: [
      { number: 1, status: "partial", section_cited: null },
      { number: 2, status: "refused", section_cited: "8(1)(j)" },
      { number: 3, status: "transferred", section_cited: null },
    ],
    fee_demanded: false,
    transferred_to: "Sample District Office",
    suggested_grounds: ["incomplete", "refused"],
  },
  hi: {
    letter_date: "2026-10-15",
    items: [
      { number: 1, status: "partial", section_cited: null },
      { number: 2, status: "refused", section_cited: "8(1)(j)" },
      { number: 3, status: "transferred", section_cited: null },
    ],
    fee_demanded: false,
    transferred_to: "नमूना ज़िला कार्यालय",
    suggested_grounds: ["incomplete", "refused"],
  },
  ta: {
    letter_date: "2026-10-15",
    items: [
      { number: 1, status: "partial", section_cited: null },
      { number: 2, status: "refused", section_cited: "8(1)(j)" },
      { number: 3, status: "transferred", section_cited: null },
    ],
    fee_demanded: false,
    transferred_to: "மாதிரி மாவட்ட அலுவலகம்",
    suggested_grounds: ["incomplete", "refused"],
  },
};

/** A fictional 1x1 PNG, standing in for a photo of the reply letter. */
export const SAMPLE_LETTER_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==",
  "base64",
);

export function baseCase(lang: Lang, overrides: Json = {}): Json {
  return {
    id: CASE_ID,
    language: lang,
    jurisdiction: null,
    status: "draft",
    authority_name: null,
    pio_address: null,
    has_applicant: false,
    via_apio: false,
    third_party: false,
    life_liberty: false,
    filing_mode: null,
    filed_on: null,
    received_on: null,
    received_estimated: false,
    reply_received_on: null,
    appeal_filed_on: null,
    questions: [],
    deadlines: [],
    created_at: "2026-10-27T10:00:00Z",
    ...overrides,
  };
}

/** Three questions in review: one accepted, one waiting, one held back as personal information. */
export function reviewQuestions(lang: Lang): Json[] {
  const f = FIXTURES[lang];
  return [
    {
      id: QUESTION_IDS[0],
      position: 1,
      original_text: f.question.original,
      rewritten_text: f.question.rewritten,
      records_requested: f.question.records,
      reason: f.question.reason,
      personal_information: false,
      suggestion: null,
      accepted: true,
    },
    {
      id: QUESTION_IDS[1],
      position: 2,
      original_text: f.second.original,
      rewritten_text: f.second.rewritten,
      records_requested: f.second.records,
      reason: f.second.reason,
      personal_information: false,
      suggestion: null,
      accepted: false,
    },
    {
      id: QUESTION_IDS[2],
      position: 3,
      original_text: f.personal.original,
      rewritten_text: "",
      records_requested: [],
      reason: f.personal.reason,
      personal_information: true,
      suggestion: f.personal.suggestion,
      accepted: false,
    },
  ];
}

export function localAuthorityName(lang: Lang): string {
  const a = FIXTURES[lang].authority;
  return lang === "ta" ? a.name_ta : lang === "hi" ? a.name_hi : a.name;
}

/** A filed case whose receipt date and deadlines are estimated. */
export function filedCase(lang: Lang, overrides: Json = {}): Json {
  return baseCase(lang, {
    jurisdiction: "tamil_nadu",
    status: "reply_due",
    authority_name: localAuthorityName(lang),
    pio_address: FIXTURES[lang].authority.address,
    has_applicant: true,
    filing_mode: "post",
    filed_on: "2026-10-27",
    received_on: "2026-11-03",
    received_estimated: true,
    questions: reviewQuestions(lang).map((q) => ({ ...q, accepted: true })),
    deadlines: [
      { kind: "pio_reply", due_on: "2026-12-03", due_at: null, estimated: true },
      { kind: "first_appeal", due_on: "2027-01-02", due_at: null, estimated: true },
    ],
    ...overrides,
  });
}

/**
 * A case filed in September whose PIO day has passed with no reply yet (reply_due): the reader,
 * the reply date and the first appeal are all open. Receipt and deadlines are estimated.
 */
export function overdueCase(lang: Lang, overrides: Json = {}): Json {
  return filedCase(lang, {
    filed_on: "2026-09-01",
    received_on: "2026-09-08",
    deadlines: [
      { kind: "pio_reply", due_on: "2026-10-08", due_at: null, estimated: true },
      { kind: "first_appeal", due_on: "2026-11-07", due_at: null, estimated: true },
    ],
    ...overrides,
  });
}

/** A case whose reply arrived on 17 Oct 2026 (status replied). */
export function repliedCase(lang: Lang): Json {
  return overdueCase(lang, {
    status: "replied",
    received_on: "2026-09-04",
    received_estimated: false,
    reply_received_on: "2026-10-17",
    deadlines: [
      { kind: "pio_reply", due_on: "2026-10-04", due_at: null, estimated: false },
      { kind: "first_appeal", due_on: "2026-11-16", due_at: null, estimated: false },
    ],
  });
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
}

function empty(route: Route) {
  return route.fulfill({ status: 204, body: "" });
}

function pdf(route: Route) {
  return route.fulfill({
    status: 200,
    headers: { "content-type": "application/pdf" },
    body: "%PDF-1.4\n% fictional sample, not a real document\n%%EOF\n",
  });
}

const fail = (route: Route, status: number, error: string) => json(route, status, { error, detail: null });

function derivedFlags(c: Json): Flag[] {
  const block = (code: string): Flag => ({ code, severity: "block", question: null, basis: null, under_challenge: false });
  const flags: Flag[] = [];
  if (!c.pio_address) flags.push(block("missing_pio_address"));
  if (!c.has_applicant) flags.push(block("missing_applicant_address"));
  if (!(c.questions as Json[]).length) flags.push(block("no_questions"));
  return flags;
}

export async function mockApi(page: Page, options: MockOptions = {}): Promise<MockApi> {
  const lang = options.lang ?? "en";
  const f = FIXTURES[lang];
  const calls: ApiCall[] = [];
  const intakeMessages: string[] = [];
  const busy = new Set(options.busyOnce ?? []);
  let current: Json | null = options.initialCase ? baseCase(lang, options.initialCase) : null;
  let nextQuestion = 0;

  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const path = url.pathname.replace(/^\/api/, "");
    const key = `${method} ${path.replace(UUID, ":id")}`;
    const raw = request.postData();
    let body: unknown = null;
    try {
      body = request.postDataJSON();
    } catch {
      body = raw;
    }
    const headers = await request.allHeaders();
    calls.push({ method, path, search: url.search, body, raw, origin: headers["origin"] });

    if (busy.has(key)) {
      busy.delete(key);
      return fail(route, 503, "busy");
    }
    const b = (body ?? {}) as Json;

    switch (key) {
      case "POST /session":
      case "PATCH /me":
        return empty(route);
      case "GET /me":
        return json(route, 200, { language: lang, cases: current ? 1 : 0 });
      case "DELETE /me":
        current = null;
        return empty(route);
      case "GET /me/export":
        return json(route, 200, { cases: current ? [current] : [] });
      case "GET /rules/tamil_nadu":
      case "GET /rules/central":
        return json(route, 200, RULES[path.split("/")[2]]);
      case "POST /authorities/search":
        return json(route, 200, [
          {
            id: AUTHORITY_ID,
            name: f.authority.name,
            name_ta: f.authority.name_ta,
            name_hi: f.authority.name_hi,
            jurisdiction: "tamil_nadu",
            pio_designation: f.authority.designation,
            pio_address: f.authority.address,
            rti_online: false,
          },
        ]);
      case "POST /cases":
        current = baseCase(lang, { language: b.language ?? lang, jurisdiction: b.jurisdiction ?? null });
        return json(route, 201, current);
      case "GET /cases":
        return json(
          route,
          200,
          current
            ? [
                {
                  id: current.id,
                  status: current.status,
                  authority_name: current.authority_name,
                  next_deadline: (current.deadlines as Json[])[0] ?? null,
                  created_at: current.created_at,
                },
              ]
            : [],
        );
    }

    if (!current) return fail(route, 404, "not_found");
    const status = String(current.status);

    switch (key) {
      case "GET /cases/:id":
        return json(route, 200, current);
      case "DELETE /cases/:id":
        current = null;
        return empty(route);
      case "POST /cases/:id/intake": {
        // The server keeps no history: the browser sends the whole conversation each time.
        const message = String(b.message ?? "");
        intakeMessages.push(message);
        const ready = message.includes("\nQ: ");
        return json(route, 200, {
          intake: {
            jurisdiction_hint: "tamil_nadu",
            authority: f.authority.name,
            time_period: "April 2026",
            records_wanted: [f.question.records[0]],
            delivery_mode: "post",
            bpl: "no",
            follow_up_questions: ready ? [] : f.followUps,
            ready_to_draft: ready,
          },
          authorities: [
            {
              id: AUTHORITY_ID,
              name: f.authority.name,
              name_ta: f.authority.name_ta,
              name_hi: f.authority.name_hi,
              jurisdiction: "tamil_nadu",
              pio_designation: f.authority.designation,
              pio_address: f.authority.address,
              rti_online: false,
            },
          ],
        });
      }
      case "PUT /cases/:id/authority":
        current = { ...current, ...b };
        return json(route, 200, current);
      case "PUT /cases/:id/applicant":
        current = { ...current, has_applicant: true };
        return empty(route);
      case "POST /cases/:id/questions": {
        const question = {
          id: QUESTION_IDS[nextQuestion % QUESTION_IDS.length],
          position: (current.questions as Json[]).length + 1,
          original_text: String(b.text),
          rewritten_text: f.question.rewritten,
          records_requested: f.question.records,
          reason: f.question.reason,
          personal_information: false,
          suggestion: null,
          accepted: false,
        };
        nextQuestion += 1;
        current = { ...current, questions: [...(current.questions as Json[]), question] };
        return json(route, 201, question);
      }
      case "PATCH /cases/:id/questions/:id": {
        const qid = path.split("/")[4];
        const questions = (current.questions as Json[]).map((q) => (q.id === qid ? { ...q, ...b } : q));
        current = { ...current, questions };
        return json(route, 200, questions.find((q) => q.id === qid));
      }
      case "DELETE /cases/:id/questions/:id": {
        const qid = path.split("/")[4];
        current = { ...current, questions: (current.questions as Json[]).filter((q) => q.id !== qid) };
        return empty(route);
      }
      case "GET /cases/:id/validation":
        return json(route, 200, { flags: options.flags ?? derivedFlags(current) });
      case "POST /cases/:id/application":
        if (options.applicationBlocked) {
          return json(route, 409, { error: "blocked", detail: { flags: options.applicationBlocked } });
        }
        return pdf(route);
      case "POST /cases/:id/filing":
        current = {
          ...current,
          status: "reply_due",
          filed_on: b.filed_on,
          filing_mode: b.filing_mode,
          received_on: b.received_on ?? "2026-11-03",
          received_estimated: !b.received_on,
          deadlines: [
            { kind: "pio_reply", due_on: "2026-12-03", due_at: null, estimated: !b.received_on },
            { kind: "first_appeal", due_on: "2027-01-02", due_at: null, estimated: !b.received_on },
          ],
        };
        return json(route, 200, current);
      case "PUT /cases/:id/receipt":
        if (status !== "reply_due") return fail(route, 409, "wrong_status");
        if (String(b.received_on) < String(current.filed_on)) return fail(route, 400, "invalid");
        current = {
          ...current,
          received_on: b.received_on,
          received_estimated: false,
          deadlines: [
            { kind: "pio_reply", due_on: "2026-11-29", due_at: null, estimated: false },
            { kind: "first_appeal", due_on: "2026-12-29", due_at: null, estimated: false },
          ],
        };
        return json(route, 200, current);
      case "POST /cases/:id/reply/read":
        if (!["reply_due", "deemed_refused", "replied"].includes(status)) return fail(route, 409, "wrong_status");
        if (!/name="consent"\r\n\r\ntrue/.test(raw ?? "")) return fail(route, 400, "consent_required");
        if (!/name="file"; filename=/.test(raw ?? "")) return fail(route, 400, "invalid");
        return json(route, 200, READINGS[lang]);
      case "POST /cases/:id/reply":
        if (!["reply_due", "deemed_refused"].includes(status)) return fail(route, 409, "wrong_status");
        current = {
          ...current,
          status: "replied",
          reply_received_on: b.received_on,
          deadlines: [
            ...(current.deadlines as Json[]).filter((d) => d.kind === "pio_reply"),
            { kind: "first_appeal", due_on: "2026-11-16", due_at: null, estimated: false },
          ],
        };
        return json(route, 200, current);
      case "POST /cases/:id/appeal": {
        if (!["replied", "deemed_refused", "appealed"].includes(status)) return fail(route, 409, "wrong_status");
        const grounds = (b.grounds as string[] | undefined) ?? [];
        if (grounds.includes("no_reply") && current.reply_received_on) return fail(route, 400, "invalid_grounds");
        if (grounds.length === 0 || !String(b.faa_address ?? "").trim()) return fail(route, 400, "invalid");
        return pdf(route);
      }
      case "POST /cases/:id/appeal/filing":
        if (!["replied", "deemed_refused"].includes(status)) return fail(route, 409, "wrong_status");
        current = {
          ...current,
          status: "appealed",
          appeal_filed_on: b.filed_on,
          deadlines: [
            ...(current.deadlines as Json[]),
            { kind: "faa_decision", due_on: "2026-11-26", due_at: null, estimated: !b.received_on },
            { kind: "second_appeal", due_on: "2027-02-24", due_at: null, estimated: !b.received_on },
          ],
        };
        return json(route, 200, current);
      case "POST /cases/:id/close":
        current = { ...current, status: "closed" };
        return json(route, 200, current);
      default:
        return fail(route, 404, "not_found");
    }
  });

  return { calls, intakeMessages, current: () => current };
}
