import { describe, expect, it, vi } from "vitest";
import { ApiError, BlockedError, apiBaseUrl, createApiClient } from "./api";
import { CASE_ID, QUESTION_ID, caseFixture, questionFixture } from "@/test/fixtures";

const BASE = "https://api.unseal.test";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function setup(...responses: Array<Response | Error>) {
  const fetchImpl = vi.fn<typeof fetch>();
  for (const r of responses) {
    if (r instanceof Error) fetchImpl.mockRejectedValueOnce(r);
    else fetchImpl.mockResolvedValueOnce(r);
  }
  return { fetchImpl, client: createApiClient({ baseUrl: BASE, fetchImpl }) };
}

function call(fetchImpl: ReturnType<typeof vi.fn<typeof fetch>>, index = 0) {
  const [url, init] = fetchImpl.mock.calls[index];
  return { url: String(url), init: init ?? {} };
}

describe("api client: requests", () => {
  it("sends credentials: include and a JSON body to POST /cases", async () => {
    const { fetchImpl, client } = setup(json(201, caseFixture({ language: "ta" })));

    const created = await client.createCase({ language: "ta", jurisdiction: "tamil_nadu" });

    const { url, init } = call(fetchImpl);
    expect(url).toBe(`${BASE}/cases`);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ language: "ta", jurisdiction: "tamil_nadu" });
    expect(created.id).toBe(CASE_ID);
  });

  it("sends credentials: include on reads too", async () => {
    const { fetchImpl, client } = setup(json(200, []));

    await client.listCases();

    const { url, init } = call(fetchImpl);
    expect(url).toBe(`${BASE}/cases`);
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
    expect(init.body).toBeUndefined();
  });

  it("returns nothing for a 204 (POST /session) and strips a trailing slash from the base URL", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient({ baseUrl: `${BASE}/`, fetchImpl });

    await expect(client.createSession("hi")).resolves.toBeUndefined();

    const { url, init } = call(fetchImpl);
    expect(url).toBe(`${BASE}/session`);
    expect(JSON.parse(String(init.body))).toEqual({ language: "hi" });
  });

  it("fills safe defaults when optional Case fields are missing", async () => {
    const partial = { ...caseFixture(), questions: undefined, deadlines: undefined };
    const { client } = setup(json(200, partial));

    const loaded = await client.getCase(CASE_ID);

    expect(loaded.questions).toEqual([]);
    expect(loaded.deadlines).toEqual([]);
  });

  it("searches authorities with the text in the body, never in the URL", async () => {
    const { fetchImpl, client } = setup(json(200, []), json(200, []));

    await client.searchAuthorities("exam cell & board", "tamil_nadu");
    await client.searchAuthorities("passport office");

    const first = call(fetchImpl, 0);
    expect(`${first.init.method} ${first.url}`).toBe(`POST ${BASE}/authorities/search`);
    expect(JSON.parse(String(first.init.body))).toEqual({
      q: "exam cell & board",
      jurisdiction: "tamil_nadu",
    });
    expect(JSON.parse(String(call(fetchImpl, 1).init.body))).toEqual({
      q: "passport office",
      jurisdiction: null,
    });
    expect(first.url).not.toContain("exam");
  });

  it("reads the new Case fields and a 48-hour next deadline", async () => {
    const summary = {
      id: CASE_ID,
      status: "reply_due",
      authority_name: null,
      next_deadline: { kind: "pio_reply", due_on: null, due_at: "2026-10-29T10:00:00Z", estimated: false },
      created_at: "2026-10-27T10:00:00Z",
    };
    const { client } = setup(json(200, [summary]), json(200, caseFixture()));

    const [listed] = await client.listCases();
    const loaded = await client.getCase(CASE_ID);

    expect(listed.next_deadline?.due_at).toBe("2026-10-29T10:00:00Z");
    expect(loaded.reply_received_on).toBeNull();
    expect(loaded.appeal_filed_on).toBeNull();
  });

  it("uploads the reply as multipart with consent and lets the browser set the boundary", async () => {
    const reading = {
      letter_date: "2026-11-20",
      items: [{ number: 1, status: "refused", section_cited: "8(1)(j)" }],
      fee_demanded: false,
      transferred_to: null,
      suggested_grounds: ["refused"],
    };
    const { fetchImpl, client } = setup(json(200, reading));
    const file = new File(["%PDF-1.7"], "reply.pdf", { type: "application/pdf" });

    const result = await client.readReply(CASE_ID, file);

    const { url, init } = call(fetchImpl);
    expect(`${init.method} ${url}`).toBe(`POST ${BASE}/cases/${CASE_ID}/reply/read`);
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("content-type")).toBeNull();
    const form = init.body as FormData;
    expect(form.get("consent")).toBe("true");
    expect((form.get("file") as File).name).toBe("reply.pdf");
    expect(result.items[0]).toEqual({ number: 1, status: "refused", section_cited: "8(1)(j)" });
    expect(result.suggested_grounds).toEqual(["refused"]);
  });

  it("defaults to the same-origin /api proxy when NEXT_PUBLIC_API_URL is unset", () => {
    const saved = process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;
    try {
      expect(apiBaseUrl()).toBe("/api");
    } finally {
      if (saved !== undefined) process.env.NEXT_PUBLIC_API_URL = saved;
    }
  });

  it("refuses an id that is not a UUID, without calling the API", async () => {
    const { fetchImpl, client } = setup();

    await expect(client.getCase("../me")).rejects.toMatchObject({ code: "invalid" });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("PATCHes a question with only the fields given", async () => {
    const { fetchImpl, client } = setup(json(200, questionFixture({ accepted: true })));

    const q = await client.updateQuestion(CASE_ID, QUESTION_ID, { accepted: true });

    const { url, init } = call(fetchImpl);
    expect(url).toBe(`${BASE}/cases/${CASE_ID}/questions/${QUESTION_ID}`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ accepted: true });
    expect(q.accepted).toBe(true);
  });

  it("returns the application PDF as a Blob", async () => {
    const pdf = new Response(new Blob(["%PDF-1.7 sample"], { type: "application/pdf" }), {
      status: 200,
      headers: { "content-type": "application/pdf" },
    });
    const { fetchImpl, client } = setup(pdf);

    const blob = await client.downloadApplication(CASE_ID, { payment_mode: "cash", place: "Chennai" });

    expect(blob.type).toBe("application/pdf");
    expect(new Headers(call(fetchImpl).init.headers).get("accept")).toBe("application/pdf");
  });
});

describe("api client: every route in docs/api.md", () => {
  const Q = QUESTION_ID;
  const C = CASE_ID;
  const caseJson = () => json(200, caseFixture());
  const noContent = () => new Response(null, { status: 204 });
  const rules = {
    application_fee: 10,
    copy_fee_per_page: 2,
    word_limit: null,
    payment_modes: ["cash"],
    filing_channels: ["post"],
    bpl_certificate_required: true,
    sources: [],
  };
  type Row = [string, (c: ReturnType<typeof createApiClient>) => Promise<unknown>, string, string, () => Response];
  const rows: Row[] = [
    ["createSession", (c) => c.createSession("ta"), "POST", "/session", noContent],
    ["getMe", (c) => c.getMe(), "GET", "/me", () => json(200, { language: "ta", cases: 2 })],
    ["updateMe", (c) => c.updateMe("hi"), "PATCH", "/me", noContent],
    ["deleteMe", (c) => c.deleteMe(), "DELETE", "/me", noContent],
    ["exportMe", (c) => c.exportMe(), "GET", "/me/export", () => json(200, { cases: [] })],
    ["getRules", (c) => c.getRules("tamil_nadu"), "GET", "/rules/tamil_nadu", () => json(200, rules)],
    ["createCase", (c) => c.createCase({ language: "en" }), "POST", "/cases", () => json(201, caseFixture())],
    ["listCases", (c) => c.listCases(), "GET", "/cases", () => json(200, [])],
    ["searchAuthorities", (c) => c.searchAuthorities("cbse", "central"), "POST", "/authorities/search", () =>
      json(200, [])],
    ["setReceipt", (c) => c.setReceipt(C, "2026-10-30"), "PUT", `/cases/${C}/receipt`, caseJson],
    ["downloadAppeal", (c) =>
      c.downloadAppeal(C, { grounds: ["no_reply"], faa_address: "Sample", details: "", delay_reason: "", place: "" }),
      "POST", `/cases/${C}/appeal`, () => new Response(new Blob(["%PDF"]), { status: 200 })],
    ["recordAppealFiling", (c) => c.recordAppealFiling(C, { filed_on: "2026-11-25", received_on: null }),
      "POST", `/cases/${C}/appeal/filing`, caseJson],
    ["getCase", (c) => c.getCase(C), "GET", `/cases/${C}`, caseJson],
    ["deleteCase", (c) => c.deleteCase(C), "DELETE", `/cases/${C}`, noContent],
    ["intake", (c) => c.intake(C, "text"), "POST", `/cases/${C}/intake`, () =>
      json(200, { intake: { follow_up_questions: [], ready_to_draft: true }, authorities: [] })],
    ["setAuthority", (c) =>
      c.setAuthority(C, {
        jurisdiction: "central",
        authority_name: "Sample Office",
        pio_address: "Sample Address",
        via_apio: false,
        third_party: false,
        life_liberty: false,
      }), "PUT", `/cases/${C}/authority`, caseJson],
    ["setApplicant", (c) => c.setApplicant(C, { name: "A", address: "B", phone: null, bpl: false }),
      "PUT", `/cases/${C}/applicant`, noContent],
    ["addQuestion", (c) => c.addQuestion(C, "why"), "POST", `/cases/${C}/questions`, () =>
      json(201, questionFixture())],
    ["updateQuestion", (c) => c.updateQuestion(C, Q, { rewritten_text: "x" }), "PATCH",
      `/cases/${C}/questions/${Q}`, () => json(200, questionFixture())],
    ["deleteQuestion", (c) => c.deleteQuestion(C, Q), "DELETE", `/cases/${C}/questions/${Q}`, noContent],
    ["getValidation", (c) => c.getValidation(C), "GET", `/cases/${C}/validation`, () => json(200, { flags: [] })],
    ["recordFiling", (c) => c.recordFiling(C, { filed_on: "2026-10-27", filing_mode: "post", received_on: null }),
      "POST", `/cases/${C}/filing`, caseJson],
    ["recordReply", (c) => c.recordReply(C, "2026-11-20"), "POST", `/cases/${C}/reply`, caseJson],
    ["closeCase", (c) => c.closeCase(C), "POST", `/cases/${C}/close`, caseJson],
  ];

  it.each(rows)("%s calls the documented method and path", async (_, invoke, method, path, respond) => {
    const { fetchImpl, client } = setup(respond());

    await invoke(client);

    const { url, init } = call(fetchImpl);
    expect(`${init.method} ${url}`).toBe(`${method} ${BASE}${path}`);
    expect(init.credentials).toBe("include");
  });

  it("sends the reply date as received_on", async () => {
    const { fetchImpl, client } = setup(json(200, caseFixture({ status: "replied" })));

    await client.recordReply(CASE_ID, "2026-11-20");

    expect(JSON.parse(String(call(fetchImpl).init.body))).toEqual({ received_on: "2026-11-20" });
  });
});

describe("api client: error mapping", () => {
  it.each([
    [503, "busy", true],
    [422, "ask_user", false],
    [422, "incomplete", true],
    [429, "rate_limited", true],
    [401, "no_session", false],
    [404, "not_found", false],
    [400, "invalid", false],
    [409, "wrong_status", false],
    [400, "invalid_grounds", false],
    [400, "invalid_payment_mode", false],
    [400, "consent_required", false],
    [400, "unreadable_file", false],
    [400, "too_many_pages", false],
    [411, "length_required", false],
    [413, "too_large", false],
  ] as const)("maps %i {error: %s} to a typed error (retryable: %s)", async (status, code, retryable) => {
    const { client } = setup(json(status, { error: code, detail: null }));

    const error = await client.listCases().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code, status, retryable });
  });

  it("maps 409 blocked to a BlockedError that carries the blocking flags", async () => {
    const flags = [
      { code: "missing_applicant_address", severity: "block", question: null, basis: null, under_challenge: false },
    ];
    const { client } = setup(json(409, { error: "blocked", detail: { flags } }));

    const error = await client
      .downloadApplication(CASE_ID, { payment_mode: "cash", place: "Chennai" })
      .catch((e: unknown) => e);

    expect(error).toBeInstanceOf(BlockedError);
    expect((error as BlockedError).code).toBe("blocked");
    expect((error as BlockedError).flags).toEqual(flags);
  });

  it("falls back to the HTTP status when the body is not JSON (a 503 from a proxy)", async () => {
    const html = new Response("<html>Service Unavailable</html>", {
      status: 503,
      headers: { "content-type": "text/html" },
    });
    const { client } = setup(html);

    await expect(client.getMe()).rejects.toMatchObject({ code: "busy", retryable: true });
  });

  it.each([
    [413, "too_large"],
    [411, "length_required"],
  ] as const)("maps a bare %i from a proxy to %s", async (status, code) => {
    const { client } = setup(new Response("<html>error</html>", { status }));

    await expect(client.readReply(CASE_ID, new File(["x"], "r.png"))).rejects.toMatchObject({ code });
  });

  it("maps a network failure to a retryable network error", async () => {
    const { client } = setup(new TypeError("Failed to fetch"));

    await expect(client.listCases()).rejects.toMatchObject({ code: "network", retryable: true });
  });

  it("rejects a response that does not match the contract", async () => {
    const { client } = setup(json(200, { id: 42 }));

    await expect(client.getCase(CASE_ID)).rejects.toMatchObject({ code: "bad_response" });
  });
});
