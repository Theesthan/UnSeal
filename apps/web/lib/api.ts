// Typed client for the UnSeal API (docs/api.md, contract v1).
//
// - Every call sends the session cookie (`credentials: "include"`). Writes need the browser's
//   Origin header, which the browser adds itself; nothing here sets it.
// - Every error becomes an ApiError with a code the UI can word in the user's language.
// - Responses are checked against lib/schemas.ts before use; ids are checked before they go
//   into a URL, so a stray value can never change the path.
import type { z } from "zod";
import {
  authoritySchema,
  blockedDetailSchema,
  caseSchema,
  caseSummarySchema,
  errorBodySchema,
  intakeResponseSchema,
  meSchema,
  questionSchema,
  replyReadingSchema,
  rulesSchema,
  validationSchema,
} from "./schemas";
import type {
  AppealBody,
  AppealFilingBody,
  ApplicantBody,
  ApplicationBody,
  Authority,
  AuthorityBody,
  Case,
  CaseSummary,
  FilingBody,
  IntakeResponse,
  Jurisdiction,
  Language,
  Me,
  Question,
  QuestionPatch,
  ReplyReading,
  Rules,
  Validation,
  ValidationFlag,
} from "./types";

export type ApiErrorCode =
  | "busy"
  | "ask_user"
  | "incomplete"
  | "blocked"
  | "rate_limited"
  | "no_session"
  | "not_found"
  | "invalid"
  | "bad_origin"
  | "wrong_status"
  | "invalid_grounds"
  | "invalid_payment_mode"
  | "consent_required"
  | "unreadable_file"
  | "too_many_pages"
  | "length_required"
  | "too_large"
  | "network"
  | "server"
  | "bad_response";

const KNOWN_CODES: ReadonlySet<string> = new Set<ApiErrorCode>([
  "busy",
  "ask_user",
  "incomplete",
  "blocked",
  "rate_limited",
  "no_session",
  "not_found",
  "invalid",
  "bad_origin",
  "wrong_status",
  "invalid_grounds",
  "invalid_payment_mode",
  "consent_required",
  "unreadable_file",
  "too_many_pages",
  "length_required",
  "too_large",
]);

// Used only when the body carries no known code (for example an HTML 503 from a proxy).
const CODE_BY_STATUS: Record<number, ApiErrorCode> = {
  400: "invalid",
  401: "no_session",
  403: "bad_origin",
  404: "not_found",
  409: "blocked",
  411: "length_required",
  413: "too_large",
  422: "ask_user",
  429: "rate_limited",
  502: "busy",
  503: "busy",
  504: "busy",
};

const RETRYABLE: ReadonlySet<ApiErrorCode> = new Set<ApiErrorCode>([
  "busy",
  "incomplete",
  "rate_limited",
  "network",
  "server",
]);

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number;
  readonly detail: unknown;

  constructor(code: ApiErrorCode, status: number, detail: unknown = null) {
    super(`UnSeal API error: ${code} (${status})`);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.detail = detail;
  }

  /** True when the same request may succeed if the user simply tries again. */
  get retryable(): boolean {
    return RETRYABLE.has(this.code);
  }
}

export class BlockedError extends ApiError {
  readonly flags: ValidationFlag[];

  constructor(flags: ValidationFlag[], detail: unknown) {
    super("blocked", 409, detail);
    this.name = "BlockedError";
    this.flags = flags;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Map an HTTP error response to a typed error. Exported for tests. */
export function toApiError(status: number, rawBody: string): ApiError {
  const body = errorBodySchema.safeParse(parseJson(rawBody));
  const bodyCode = body.success && KNOWN_CODES.has(body.data.error) ? body.data.error : null;
  const code = (bodyCode as ApiErrorCode | null) ?? CODE_BY_STATUS[status] ?? "server";
  const detail = body.success ? (body.data.detail ?? null) : null;
  if (code === "blocked") {
    const parsed = blockedDetailSchema.safeParse(detail);
    return new BlockedError(parsed.success ? parsed.data.flags : [], detail);
  }
  return new ApiError(code, status, detail);
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function idSegment(id: string): string {
  if (!UUID.test(id)) throw new ApiError("invalid", 0, { id: "not a UUID" });
  return id;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  body?: unknown;
  /** A multipart body; the browser sets its Content-Type (with the boundary) and length. */
  form?: FormData;
  accept?: string;
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export interface ApiClient {
  createSession(language: Language): Promise<void>;
  getMe(): Promise<Me>;
  updateMe(language: Language): Promise<void>;
  deleteMe(): Promise<void>;
  exportMe(): Promise<Blob>;
  getRules(jurisdiction: Jurisdiction): Promise<Rules>;
  searchAuthorities(query: string, jurisdiction?: Jurisdiction): Promise<Authority[]>;
  createCase(body: { language: Language; jurisdiction?: Jurisdiction }): Promise<Case>;
  listCases(): Promise<CaseSummary[]>;
  getCase(id: string): Promise<Case>;
  deleteCase(id: string): Promise<void>;
  intake(id: string, message: string): Promise<IntakeResponse>;
  setAuthority(id: string, body: AuthorityBody): Promise<Case>;
  setApplicant(id: string, body: ApplicantBody): Promise<void>;
  addQuestion(id: string, text: string): Promise<Question>;
  updateQuestion(id: string, questionId: string, patch: QuestionPatch): Promise<Question>;
  deleteQuestion(id: string, questionId: string): Promise<void>;
  getValidation(id: string): Promise<Validation>;
  downloadApplication(id: string, body: ApplicationBody): Promise<Blob>;
  recordFiling(id: string, body: FilingBody): Promise<Case>;
  recordReply(id: string, receivedOn: string): Promise<Case>;
  closeCase(id: string): Promise<Case>;
  setReceipt(id: string, receivedOn: string): Promise<Case>;
  downloadAppeal(id: string, body: AppealBody): Promise<Blob>;
  recordAppealFiling(id: string, body: AppealFilingBody): Promise<Case>;
  readReply(id: string, file: Blob): Promise<ReplyReading>;
}

// Called through a wrapper so `fetch` is looked up at call time and never invoked unbound.
const globalFetch: typeof fetch = (input, init) => fetch(input, init);

export function createApiClient({ baseUrl, fetchImpl = globalFetch }: ApiClientOptions): ApiClient {
  const base = baseUrl.replace(/\/+$/, "");

  async function send(method: Method, path: string, opts: RequestOptions = {}): Promise<Response> {
    const headers: Record<string, string> = { Accept: opts.accept ?? "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    const body = opts.form ?? (opts.body === undefined ? undefined : JSON.stringify(opts.body));
    let response: Response;
    try {
      response = await fetchImpl(`${base}${path}`, {
        method,
        headers,
        credentials: "include",
        cache: "no-store",
        body,
      });
    } catch (cause) {
      throw new ApiError("network", 0, cause instanceof Error ? cause.name : null);
    }
    if (!response.ok) throw toApiError(response.status, await response.text());
    return response;
  }

  async function json<S extends z.ZodType>(
    schema: S,
    method: Method,
    path: string,
    opts?: RequestOptions,
  ): Promise<z.output<S>> {
    const response = await send(method, path, opts);
    const parsed = schema.safeParse(parseJson(await response.text()));
    if (!parsed.success) throw new ApiError("bad_response", response.status);
    return parsed.data;
  }

  async function empty(method: Method, path: string, opts?: RequestOptions): Promise<void> {
    await send(method, path, opts);
  }

  async function blob(method: Method, path: string, opts?: RequestOptions): Promise<Blob> {
    const response = await send(method, path, opts);
    return response.blob();
  }

  const casePath = (id: string) => `/cases/${idSegment(id)}`;
  const run = <T>(fn: () => Promise<T>): Promise<T> => {
    try {
      return fn();
    } catch (error) {
      return Promise.reject(error);
    }
  };

  return {
    createSession: (language) => empty("POST", "/session", { body: { language } }),
    getMe: () => json(meSchema, "GET", "/me"),
    updateMe: (language) => empty("PATCH", "/me", { body: { language } }),
    deleteMe: () => empty("DELETE", "/me"),
    exportMe: () => blob("GET", "/me/export"),
    getRules: (jurisdiction) =>
      json(rulesSchema, "GET", `/rules/${encodeURIComponent(jurisdiction)}`),
    // The search text goes in the body: it is whatever the user typed, so never in a URL.
    searchAuthorities: (query, jurisdiction) =>
      json(authoritySchema.array(), "POST", "/authorities/search", {
        body: { q: query, jurisdiction: jurisdiction ?? null },
      }),
    createCase: (body) => json(caseSchema, "POST", "/cases", { body }),
    listCases: () => json(caseSummarySchema.array(), "GET", "/cases"),
    getCase: (id) => run(() => json(caseSchema, "GET", casePath(id))),
    deleteCase: (id) => run(() => empty("DELETE", casePath(id))),
    intake: (id, message) =>
      run(() => json(intakeResponseSchema, "POST", `${casePath(id)}/intake`, { body: { message } })),
    setAuthority: (id, body) =>
      run(() => json(caseSchema, "PUT", `${casePath(id)}/authority`, { body })),
    setApplicant: (id, body) => run(() => empty("PUT", `${casePath(id)}/applicant`, { body })),
    addQuestion: (id, text) =>
      run(() => json(questionSchema, "POST", `${casePath(id)}/questions`, { body: { text } })),
    updateQuestion: (id, questionId, patch) =>
      run(() =>
        json(questionSchema, "PATCH", `${casePath(id)}/questions/${idSegment(questionId)}`, {
          body: patch,
        }),
      ),
    deleteQuestion: (id, questionId) =>
      run(() => empty("DELETE", `${casePath(id)}/questions/${idSegment(questionId)}`)),
    getValidation: (id) => run(() => json(validationSchema, "GET", `${casePath(id)}/validation`)),
    downloadApplication: (id, body) =>
      run(() =>
        blob("POST", `${casePath(id)}/application`, { body, accept: "application/pdf" }),
      ),
    recordFiling: (id, body) =>
      run(() => json(caseSchema, "POST", `${casePath(id)}/filing`, { body })),
    recordReply: (id, receivedOn) =>
      run(() =>
        json(caseSchema, "POST", `${casePath(id)}/reply`, { body: { received_on: receivedOn } }),
      ),
    closeCase: (id) => run(() => json(caseSchema, "POST", `${casePath(id)}/close`)),
    setReceipt: (id, receivedOn) =>
      run(() =>
        json(caseSchema, "PUT", `${casePath(id)}/receipt`, { body: { received_on: receivedOn } }),
      ),
    downloadAppeal: (id, body) =>
      run(() => blob("POST", `${casePath(id)}/appeal`, { body, accept: "application/pdf" })),
    recordAppealFiling: (id, body) =>
      run(() => json(caseSchema, "POST", `${casePath(id)}/appeal/filing`, { body })),
    readReply: (id, file) =>
      run(() => {
        // consent=true is sent only because the user ticked the consent box before this call.
        const form = new FormData();
        form.append("file", file);
        form.append("consent", "true");
        return json(replyReadingSchema, "POST", `${casePath(id)}/reply/read`, { form });
      }),
  };
}

/**
 * Base URL of the API. By default the browser calls /api on the web app's own origin and Next.js
 * proxies it to API_ORIGIN (next.config.ts), so the session cookie stays first-party.
 * NEXT_PUBLIC_API_URL (public, never a secret) points the browser straight at an API instead.
 */
export function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "/api";
}

export const api: ApiClient = createApiClient({ baseUrl: apiBaseUrl() });
