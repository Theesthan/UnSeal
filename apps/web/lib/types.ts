// Shapes of the UnSeal API (docs/api.md, contract v1). Runtime checks live in lib/schemas.ts.

export const LANGUAGES = ["en", "hi", "ta"] as const;
export type Language = (typeof LANGUAGES)[number];

export const JURISDICTIONS = ["central", "tamil_nadu"] as const;
export type Jurisdiction = (typeof JURISDICTIONS)[number];

export const CASE_STATUSES = [
  "draft",
  "filed",
  "reply_due",
  "replied",
  "deemed_refused",
  "appealed",
  "closed",
] as const;
export type CaseStatus = (typeof CASE_STATUSES)[number];

export const DEADLINE_KINDS = [
  "pio_reply",
  "first_appeal",
  "faa_decision",
  "second_appeal",
] as const;
export type DeadlineKind = (typeof DEADLINE_KINDS)[number];

export const FLAG_CODES = [
  "missing_pio_address",
  "missing_applicant_address",
  "no_questions",
  "over_word_limit",
  "personal_information",
  "opinion_ask",
] as const;
export type FlagCode = (typeof FLAG_CODES)[number];

export const FILING_MODES = ["rti_online", "post", "in_person"] as const;
export type FilingMode = (typeof FILING_MODES)[number];

export interface Question {
  id: string;
  position: number;
  original_text: string;
  rewritten_text: string;
  records_requested: string[];
  reason: string;
  personal_information: boolean;
  suggestion: string | null;
  accepted: boolean;
}

export interface Deadline {
  // A string, not DeadlineKind: an unknown kind from a newer API still renders.
  kind: string;
  due_on: string | null;
  due_at: string | null;
  estimated: boolean;
}

export interface Case {
  id: string;
  language: string;
  jurisdiction: string | null;
  // A string, not CaseStatus: an unknown status shows a fallback, never a blank card.
  status: string;
  authority_name: string | null;
  pio_address: string | null;
  has_applicant: boolean;
  via_apio: boolean;
  third_party: boolean;
  life_liberty: boolean;
  filing_mode: string | null;
  filed_on: string | null;
  received_on: string | null;
  received_estimated: boolean;
  reply_received_on: string | null;
  appeal_filed_on: string | null;
  questions: Question[];
  deadlines: Deadline[];
  created_at: string;
}

export interface CaseSummary {
  id: string;
  status: string;
  authority_name: string | null;
  next_deadline: {
    kind: string;
    due_on: string | null;
    due_at: string | null;
    estimated: boolean;
  } | null;
  created_at: string;
}

export interface Authority {
  id: string;
  name: string;
  name_ta: string | null;
  name_hi: string | null;
  jurisdiction: string;
  pio_designation: string | null;
  pio_address: string | null;
  rti_online: boolean;
}

export interface Intake {
  jurisdiction_hint: string;
  authority: string | null;
  time_period: string | null;
  records_wanted: string[];
  delivery_mode: string;
  bpl: string;
  follow_up_questions: string[];
  ready_to_draft: boolean;
}

export interface IntakeResponse {
  intake: Intake;
  authorities: Authority[];
}

export interface RuleSource {
  rule: string;
  basis: string;
  source_url: string;
  checked_on: string;
  recheck: boolean;
}

export interface Rules {
  application_fee: number;
  copy_fee_per_page: number;
  word_limit: number | null;
  payment_modes: string[];
  filing_channels: string[];
  bpl_certificate_required: boolean;
  sources: RuleSource[];
}

export interface ValidationFlag {
  // A string, not FlagCode: an unknown code is worded generically instead of crashing.
  code: string;
  severity: "warn" | "block";
  // 0-based index into the case's questions (sorted by position), or null for the whole case.
  question: number | null;
  basis: string | null;
  under_challenge: boolean;
}

export interface Validation {
  flags: ValidationFlag[];
}

export interface Me {
  language: string;
  cases: number;
}

export interface AuthorityBody {
  jurisdiction: Jurisdiction;
  authority_name: string;
  pio_address: string;
  via_apio: boolean;
  third_party: boolean;
  life_liberty: boolean;
}

export interface ApplicantBody {
  name: string;
  address: string;
  phone: string | null;
  bpl: boolean;
}

export interface QuestionPatch {
  rewritten_text?: string;
  accepted?: boolean;
}

export interface ApplicationBody {
  payment_mode: string;
  place: string;
}

export interface FilingBody {
  filed_on: string;
  filing_mode: string;
  received_on: string | null;
}

export const REPLY_ITEM_STATUSES = ["given", "refused", "partial", "transferred", "unclear"] as const;

export interface ReplyItem {
  number: number;
  // A string, not a union: an unknown status from a newer API is shown as "not clear".
  status: string;
  section_cited: string | null;
}

export interface ReplyReading {
  letter_date: string | null;
  items: ReplyItem[];
  fee_demanded: boolean;
  transferred_to: string | null;
  suggested_grounds: string[];
}

export interface AppealBody {
  grounds: string[];
  faa_address: string;
  details: string;
  delay_reason: string;
  place: string;
}

export interface AppealFilingBody {
  filed_on: string;
  received_on: string | null;
}
