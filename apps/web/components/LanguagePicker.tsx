"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { api, isApiError } from "@/lib/api";
import { LANGUAGE_NAMES } from "@/lib/i18n-core";
import { hasSession } from "@/lib/session-flag";
import { LANGUAGES, type Language } from "@/lib/types";

interface PickerProps {
  lang: Language;
  label: string;
}

const pill =
  "inline-flex min-h-11 min-w-11 items-center justify-center rounded-full px-3 py-1.5 text-base font-semibold";

function PickerList({ lang, label, hrefFor, onPick }: PickerProps & {
  hrefFor: (l: Language) => string;
  onPick?: (l: Language) => void;
}) {
  return (
    <nav aria-label={label}>
      <ul className="flex flex-wrap gap-1 rounded-full bg-canvas p-1">
        {LANGUAGES.map((l) => (
          <li key={l}>
            <Link
              href={hrefFor(l)}
              lang={l}
              hrefLang={l}
              aria-current={l === lang ? "true" : undefined}
              onClick={() => onPick?.(l)}
              className={`${pill} ${
                l === lang ? "bg-brand text-white" : "text-ink hover:bg-brand-soft"
              }`}
            >
              {LANGUAGE_NAMES[l]}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Shown while the current path is not yet known (dynamic routes): links to each home page. */
export function LanguagePickerFallback({ lang, label }: PickerProps) {
  return <PickerList lang={lang} label={label} hrefFor={(l) => `/${l}`} />;
}

/** Switches language on the same page; the case id in the query string is kept. */
export function LanguagePicker({ lang, label }: PickerProps) {
  const pathname = usePathname() ?? `/${lang}`;
  const search = useSearchParams()?.toString() ?? "";

  function hrefFor(l: Language): string {
    const rest = pathname.split("/").slice(2).join("/");
    return `/${l}${rest ? `/${rest}` : ""}${search ? `?${search}` : ""}`;
  }

  function rememberLanguage(l: Language) {
    if (l === lang || !hasSession()) return;
    // Best effort: the UI language comes from the URL, so a failed sync changes nothing on
    // screen; it only affects the language of later reminders, which the next switch retries.
    api.updateMe(l).catch((error: unknown) => {
      if (!isApiError(error)) throw error;
    });
  }

  return <PickerList lang={lang} label={label} hrefFor={hrefFor} onPick={rememberLanguage} />;
}
