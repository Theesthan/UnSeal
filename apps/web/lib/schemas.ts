// Runtime checks for API responses (docs/api.md). Lenient where the contract allows growth
// (unknown status, flag code or deadline kind stays a string), strict on structure.
import { z } from "zod";

const text = z.string();
const nullableText = z.string().nullable().optional().default(null);
const flag = z.boolean().optional().default(false);

export const questionSchema = z.object({
  id: text,
  position: z.number(),
  original_text: text,
  rewritten_text: z
    .string()
    .nullable()
    .optional()
    .transform((v) => v ?? ""),
  records_requested: z.array(text).optional().default([]),
  reason: z
    .string()
    .nullable()
    .optional()
    .transform((v) => v ?? ""),
  personal_information: flag,
  suggestion: nullableText,
  accepted: flag,
});

export const deadlineSchema = z.object({
  kind: text,
  due_on: nullableText,
  due_at: nullableText,
  estimated: flag,
});

export const caseSchema = z.object({
  id: text,
  language: text,
  jurisdiction: nullableText,
  status: text,
  authority_name: nullableText,
  pio_address: nullableText,
  has_applicant: flag,
  via_apio: flag,
  third_party: flag,
  life_liberty: flag,
  filing_mode: nullableText,
  filed_on: nullableText,
  received_on: nullableText,
  received_estimated: flag,
  reply_received_on: nullableText,
  appeal_filed_on: nullableText,
  questions: z
    .array(questionSchema)
    .optional()
    .default([])
    .transform((qs) => [...qs].sort((a, b) => a.position - b.position)),
  deadlines: z.array(deadlineSchema).optional().default([]),
  created_at: text,
});

export const caseSummarySchema = z.object({
  id: text,
  status: text,
  authority_name: nullableText,
  next_deadline: z
    .object({ kind: text, due_on: nullableText, due_at: nullableText, estimated: flag })
    .nullable()
    .optional()
    .default(null),
  created_at: text,
});

export const authoritySchema = z.object({
  id: text,
  name: text,
  name_ta: nullableText,
  name_hi: nullableText,
  jurisdiction: text,
  pio_designation: nullableText,
  pio_address: nullableText,
  rti_online: flag,
});

export const intakeResponseSchema = z.object({
  intake: z.object({
    jurisdiction_hint: z.string().optional().default("unknown"),
    authority: nullableText,
    time_period: nullableText,
    records_wanted: z.array(text).optional().default([]),
    delivery_mode: z.string().optional().default("unknown"),
    bpl: z.string().optional().default("unknown"),
    follow_up_questions: z.array(text).optional().default([]),
    ready_to_draft: flag,
  }),
  authorities: z.array(authoritySchema).optional().default([]),
});

export const ruleSourceSchema = z.object({
  rule: text,
  basis: text,
  source_url: text,
  checked_on: text,
  recheck: flag,
});

export const rulesSchema = z.object({
  application_fee: z.number(),
  copy_fee_per_page: z.number(),
  word_limit: z.number().nullable().optional().default(null),
  payment_modes: z.array(text),
  filing_channels: z.array(text),
  bpl_certificate_required: flag,
  sources: z.array(ruleSourceSchema).optional().default([]),
});

export const validationFlagSchema = z.object({
  code: text,
  severity: z.enum(["warn", "block"]).catch("warn"),
  question: z.number().int().nonnegative().nullable().optional().default(null),
  basis: nullableText,
  under_challenge: flag,
});

export const validationSchema = z.object({
  flags: z.array(validationFlagSchema).optional().default([]),
});

export const replyReadingSchema = z.object({
  letter_date: nullableText,
  items: z
    .array(
      z.object({
        number: z.number().int(),
        status: text,
        section_cited: nullableText,
      }),
    )
    .optional()
    .default([]),
  fee_demanded: flag,
  transferred_to: nullableText,
  suggested_grounds: z.array(text).optional().default([]),
});

export const meSchema = z.object({
  language: text,
  cases: z.number(),
});

export const errorBodySchema = z.object({
  error: z.string(),
  detail: z.unknown().optional(),
});

export const blockedDetailSchema = z.object({
  flags: z.array(validationFlagSchema).optional().default([]),
});
