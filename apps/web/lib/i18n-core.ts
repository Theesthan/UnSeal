// Language helpers that are safe to use in client components (no dictionaries imported here, so
// a client bundle never carries all three languages).
import { LANGUAGES, type Language } from "./types";

export const DEFAULT_LANGUAGE: Language = "en";

/** Each language named in its own script, for the language picker. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  en: "English",
  hi: "हिन्दी",
  ta: "தமிழ்",
};

const LOCALES: Record<Language, string> = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };
const INDIA_TIME_ZONE = "Asia/Kolkata";
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isLanguage(value: string): value is Language {
  return (LANGUAGES as readonly string[]).includes(value);
}

/** Fill `{name}` placeholders; an unknown placeholder stays visible rather than vanishing. */
export function format(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    Object.prototype.hasOwnProperty.call(vars, key) ? String(vars[key]) : whole,
  );
}

/**
 * Format an India calendar date (`YYYY-MM-DD`) in the UI language. The date is built in UTC and
 * printed in UTC, so no browser time zone can move it to the previous or next day.
 */
export function formatDate(iso: string, lang: Language): string {
  const match = ISO_DATE.exec(iso);
  if (!match) return iso;
  const [, y, m, d] = match;
  const date = new Date(Date.UTC(Number(y), Number(m) - 1, Number(d)));
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

/** Format a UTC timestamp (the 48-hour track) in India time. */
export function formatDateTime(iso: string, lang: Language): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: INDIA_TIME_ZONE,
  }).format(date);
}

/** Today's date in India as `YYYY-MM-DD`, for date inputs (a default the user can change). */
export function todayInIndia(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: INDIA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  return parts;
}

/** The India calendar day of a UTC timestamp (for example a case's created_at). */
export function formatDayOf(isoTimestamp: string, lang: Language): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: INDIA_TIME_ZONE,
  }).format(date);
}
