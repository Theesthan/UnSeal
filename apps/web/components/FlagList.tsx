"use client";

import { useI18n } from "./I18nProvider";
import { AlertIcon, CheckIcon } from "./icons";
import { format } from "@/lib/i18n-core";
import type { ValidationFlag } from "@/lib/types";

export interface FlagListProps {
  flags: ValidationFlag[];
}

/** Validator flags (FR-3) worded in the user's language; blocking flags come first. */
export function FlagList({ flags }: FlagListProps) {
  const { t } = useI18n();

  if (flags.length === 0) {
    return (
      <p role="status" className="box-ok flex items-center gap-2 font-semibold">
        <CheckIcon />
        {t.flow.check.noFlags}
      </p>
    );
  }

  const sorted = [...flags].sort(
    (a, b) => Number(b.severity === "block") - Number(a.severity === "block"),
  );
  const codes = t.flags.codes as Record<string, string>;

  return (
    <ul className="space-y-3">
      {sorted.map((flag, index) => {
        const blocking = flag.severity === "block";
        return (
          <li
            key={`${flag.code}-${flag.question ?? "case"}-${index}`}
            className={blocking ? "box-danger" : "box-warn"}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`badge ${blocking ? "bg-danger text-white" : "bg-sun text-ink"}`}
              >
                <AlertIcon className="h-4 w-4 shrink-0" />
                {t.flags.severity[flag.severity]}
              </span>
              {flag.question !== null && (
                <span className="badge border border-current">
                  {format(t.flags.forQuestion, { n: flag.question + 1 })}
                </span>
              )}
            </div>
            <p className="mt-2 break-words font-medium text-ink">
              {codes[flag.code] ?? format(t.flags.unknown, { code: flag.code })}
            </p>
            {flag.basis && (
              <p className="mt-1 text-sm text-ink">{format(t.flags.basis, { basis: flag.basis })}</p>
            )}
            {flag.under_challenge && <p className="mt-1 text-sm text-ink">{t.flags.underChallenge}</p>}
          </li>
        );
      })}
    </ul>
  );
}
