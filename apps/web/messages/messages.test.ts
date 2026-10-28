import { describe, expect, it } from "vitest";
import { en } from "./en";
import { hi } from "./hi";
import { ta } from "./ta";
import { CASE_STATUSES, DEADLINE_KINDS, FILING_MODES, FLAG_CODES } from "@/lib/types";
import { SAMPLES } from "@/lib/samples";

type Leaf = { path: string; value: string };

function leaves(node: unknown, path = ""): Leaf[] {
  if (typeof node === "string") return [{ path, value: node }];
  if (Array.isArray(node)) return node.flatMap((v, i) => leaves(v, `${path}[${i}]`));
  if (node && typeof node === "object") {
    return Object.entries(node).flatMap(([k, v]) => leaves(v, path ? `${path}.${k}` : k));
  }
  throw new Error(`unexpected value at ${path}`);
}

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
const ALL = { en, hi, ta };
// Built from its code point so this file never contains the character it bans.
const EM_DASH = String.fromCodePoint(0x2014);

// Payment mode codes in apps/api/src/unseal/rules/data/*.json (central and tamil_nadu).
const PAYMENT_MODES = [
  "cash",
  "demand_draft",
  "bankers_cheque",
  "indian_postal_order",
  "electronic",
  "court_fee_stamp",
  "postal_money_order",
];

describe("message dictionaries", () => {
  it.each([
    ["hi", hi],
    ["ta", ta],
  ] as const)("%s has exactly the English keys, the same placeholders and no empty strings", (_, dict) => {
    const base = leaves(en);
    const other = leaves(dict);
    expect(other.map((l) => l.path)).toEqual(base.map((l) => l.path));
    for (const [i, leaf] of other.entries()) {
      expect(leaf.value.trim(), leaf.path).not.toBe("");
      expect(placeholders(leaf.value), leaf.path).toEqual(placeholders(base[i].value));
    }
  });

  it("never uses an em dash", () => {
    for (const [lang, dict] of Object.entries(ALL)) {
      for (const leaf of leaves(dict)) {
        expect(leaf.value.includes(EM_DASH), `${lang}.${leaf.path}`).toBe(false);
      }
    }
  });

  it("uses the fixed glossary terms for the Act and the Public Information Officer", () => {
    expect(ta.landing.actName).toBe("தகவல் பெறும் உரிமைச் சட்டம், 2005");
    expect(hi.landing.actName).toBe("सूचना का अधिकार अधिनियम, 2005");
    // Tamil inflects the term (அலுவலர் -> அலுவலரின்), so check the glossary's `match` stem,
    // exactly as apps/api/src/unseal/llm/glossary.json does for model output.
    const taPioStem = "பொதுத் தகவல் அலுவலர";
    expect(ta.flow.authority.addressLabel).toContain(taPioStem);
    expect(hi.flow.authority.addressLabel).toContain("लोक सूचना अधिकारी");
    expect(ta.timeline.deadlines.pio_reply).toContain(taPioStem);
    expect(ta.flow.authority.hint).not.toContain("பொது தகவல்");
    expect(hi.timeline.deadlines.pio_reply).toContain("लोक सूचना अधिकारी");
  });

  it("labels every flag code, status, deadline kind, filing mode and payment mode", () => {
    for (const dict of Object.values(ALL)) {
      for (const code of FLAG_CODES) expect(dict.flags.codes[code]).toBeTruthy();
      for (const s of CASE_STATUSES) expect(dict.timeline.statuses[s]).toBeTruthy();
      for (const k of DEADLINE_KINDS) expect(dict.timeline.deadlines[k]).toBeTruthy();
      for (const m of FILING_MODES) expect(dict.filingChannels[m]).toBeTruthy();
      for (const p of PAYMENT_MODES) {
        expect((dict.paymentModes as Record<string, string>)[p]).toBeTruthy();
      }
    }
  });

  it("keeps Hindi first-person and second-person text gender-neutral", () => {
    // Masculine or feminine verb endings that assume who the user is.
    const gendered = /(दूँगा|दूँगी|दूंगा|दूंगी|चाहता हूँ|चाहती हूँ|करूँगा|करूँगी|सकता हूँ|सकती हूँ|चाहती हैं|आएँगी|गया हूँ|गई हूँ)/;
    for (const leaf of leaves(hi)) {
      expect(gendered.test(leaf.value), `hi.${leaf.path}: ${leaf.value}`).toBe(false);
    }
    // The Hindi sample case is shown to every voter, so it follows the same rule.
    const sampleText = JSON.stringify(SAMPLES["ward-road"]);
    expect(gendered.test(sampleText), sampleText.match(gendered)?.[0]).toBe(false);
  });

  it("words every API error code in every language", () => {
    const codes = [
      "busy",
      "ask_user",
      "incomplete",
      "blocked",
      "rate_limited",
      "no_session",
      "not_found",
      "invalid",
      "network",
      "wrong_status",
      "invalid_grounds",
      "invalid_payment_mode",
      "consent_required",
      "unreadable_file",
      "too_many_pages",
      "length_required",
      "too_large",
    ];
    for (const [lang, dict] of Object.entries(ALL)) {
      for (const code of codes) {
        expect((dict.errors as Record<string, string>)[code], `${lang}.errors.${code}`).toBeTruthy();
      }
    }
  });

  it("labels every appeal ground and every reply-reader status", () => {
    for (const dict of Object.values(ALL)) {
      for (const g of ["no_reply", "incomplete", "refused", "fee_demanded"]) {
        expect((dict.appeal.grounds as Record<string, string>)[g]).toBeTruthy();
      }
      for (const s of ["given", "refused", "partial", "transferred", "unclear"]) {
        expect((dict.replyReader.statuses as Record<string, string>)[s]).toBeTruthy();
      }
    }
  });

  it("warns in every language not to type name, address or phone into free text", () => {
    for (const dict of Object.values(ALL)) expect(dict.flow.noPersonalDetails).toBeTruthy();
    expect(en.flow.noPersonalDetails).toContain("name, address or phone number");
  });

  it("carries the disclaimer footer in English on every language", () => {
    for (const dict of Object.values(ALL)) {
      expect(dict.common.footer).toBe("Prepared with UnSeal. Not legal advice.");
    }
  });
});
