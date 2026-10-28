import { describe, expect, it } from "vitest";
import { format, formatDate, formatDateTime, formatDayOf, isLanguage, todayInIndia } from "./i18n-core";

describe("format", () => {
  it("fills placeholders and leaves unknown ones visible", () => {
    expect(format("Question {n} of {total}", { n: 2 })).toBe("Question 2 of {total}");
  });
});

describe("isLanguage", () => {
  it("accepts only en, hi and ta", () => {
    expect(["en", "hi", "ta", "fr", ""].map(isLanguage)).toEqual([true, true, true, false, false]);
  });
});

describe("formatDate", () => {
  it("formats an ISO date without shifting the day, in each language", () => {
    expect(formatDate("2026-12-03", "en")).toBe("3 December 2026");
    expect(formatDate("2026-12-03", "hi")).toContain("दिसंबर");
    expect(formatDate("2026-12-03", "ta")).toContain("டிசம்பர்");
  });

  it("returns the raw text for a malformed date instead of 'Invalid Date'", () => {
    expect(formatDate("not-a-date", "en")).toBe("not-a-date");
  });
});

describe("todayInIndia and formatDayOf", () => {
  it("use the India calendar day, not the UTC one", () => {
    // 20:00 UTC on 31 Dec is already 1 Jan in India (UTC+5:30).
    const lateUtc = new Date("2026-12-31T20:00:00Z");
    expect(todayInIndia(lateUtc)).toBe("2027-01-01");
    expect(formatDayOf("2026-12-31T20:00:00Z", "en")).toBe("1 January 2027");
    expect(formatDayOf("garbage", "en")).toBe("garbage");
  });
});

describe("formatDateTime", () => {
  it("shows a UTC timestamp in India time", () => {
    expect(formatDateTime("2026-10-29T10:00:00Z", "en")).toMatch(/29 October 2026.*3:30/);
  });
});
