// Fictional fixtures for unit tests. No real person, address or case.
import type { Case, Question } from "@/lib/types";

export const CASE_ID = "3f0c9a8e-2b1d-4c5e-9f7a-1a2b3c4d5e6f";
export const QUESTION_ID = "9b2e4c1a-7d3f-4e8a-b6c5-0d1e2f3a4b5c";

export function questionFixture(overrides: Partial<Question> = {}): Question {
  return {
    id: QUESTION_ID,
    position: 1,
    original_text: "Why is my mark so low?",
    rewritten_text:
      "Provide a certified copy of my evaluated answer script for Mathematics II, April 2026 session.",
    records_requested: ["Certified copy of the evaluated answer script", "Mark list"],
    reason: "Asks for a record the office holds instead of a reason.",
    personal_information: false,
    suggestion: null,
    accepted: false,
    ...overrides,
  };
}

export function caseFixture(overrides: Partial<Case> = {}): Case {
  return {
    id: CASE_ID,
    language: "en",
    jurisdiction: "tamil_nadu",
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
