"use client";

import { useI18n } from "./I18nProvider";
import { AlertIcon, CheckIcon } from "./icons";
import { format, formatDate } from "@/lib/i18n-core";
import type { Rules } from "@/lib/types";

interface FilingChecklistProps {
  rules: Rules;
  authorityName: string | null;
  pioAddress: string | null;
  contentLang?: string;
}

/** Fee, payment modes, where to send it and proof to keep. Every value comes from GET /rules. */
export function FilingChecklist({ rules, authorityName, pioAddress, contentLang }: FilingChecklistProps) {
  const { t, lang } = useI18n();
  const c = t.checklist;
  const modes = t.paymentModes as Record<string, string>;
  const channels = t.filingChannels as Record<string, string>;
  const needsRecheck = rules.sources.some((s) => s.recheck);

  return (
    <section aria-labelledby="checklist-title" className="card space-y-5">
      <h3 id="checklist-title" className="text-xl font-bold text-ink">
        {c.title}
      </h3>

      <div className="space-y-1">
        <p className="text-lg font-bold text-ink">{format(c.fee, { fee: rules.application_fee })}</p>
        <p>
          {c.feeBpl} {rules.bpl_certificate_required && c.feeBplCertificate}
        </p>
        <p className="text-muted">{format(c.copyFee, { fee: rules.copy_fee_per_page })}</p>
      </div>

      <div>
        <h4 className="font-bold text-ink">{c.paymentModes}</h4>
        <ul className="mt-2 flex flex-wrap gap-2">
          {rules.payment_modes.map((m) => (
            <li key={m} className="badge border border-line bg-canvas text-ink">
              {modes[m] ?? m}
            </li>
          ))}
        </ul>
      </div>

      {(authorityName || pioAddress) && (
        <div>
          <h4 className="font-bold text-ink">{c.where}</h4>
          <address lang={contentLang} className="mt-1 not-italic break-words whitespace-pre-line">
            {[authorityName, pioAddress].filter(Boolean).join("\n")}
          </address>
        </div>
      )}

      <div>
        <h4 className="font-bold text-ink">{c.channels}</h4>
        <ul className="mt-2 flex flex-wrap gap-2">
          {rules.filing_channels.map((ch) => (
            <li key={ch} className="badge border border-line bg-canvas text-ink">
              {channels[ch] ?? ch}
            </li>
          ))}
        </ul>
      </div>

      {rules.word_limit !== null && <p>{format(c.wordLimit, { limit: rules.word_limit })}</p>}

      <div>
        <h4 className="font-bold text-ink">{c.proof}</h4>
        <ul className="mt-2 space-y-1">
          {c.proofItems.map((item) => (
            <li key={item} className="flex gap-2">
              <CheckIcon className="mt-1 h-5 w-5 shrink-0 text-brand" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {needsRecheck && (
        <p className="box-warn flex gap-2">
          <AlertIcon />
          <span>{c.recheck}</span>
        </p>
      )}
      <p className="box-info font-semibold">{c.confirm}</p>

      {rules.sources.length > 0 && (
        <details className="text-sm">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-semibold text-brand">
            {c.sources}
          </summary>
          <ul className="mt-2 space-y-2">
            {rules.sources.map((s) => (
              <li key={`${s.rule}-${s.source_url}`} lang="en" className="break-words">
                <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="underline">
                  {s.basis}
                </a>{" "}
                <span lang={lang} className="text-muted">
                  ({format(c.checkedOn, { date: formatDate(s.checked_on, lang) })})
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
