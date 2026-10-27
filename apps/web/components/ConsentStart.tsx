"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "./ErrorNotice";
import { useI18n } from "./I18nProvider";
import { ArrowIcon, ShieldIcon } from "./icons";
import { api } from "@/lib/api";
import { markSessionStarted } from "@/lib/session-flag";
import { useAction } from "@/lib/use-action";

/** The privacy notice and consent (DPDP principles). No session starts until it is accepted. */
export function ConsentStart() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const ids = useId();
  const [agreed, setAgreed] = useState(false);
  const [showError, setShowError] = useState(false);
  const start = useAction(async () => {
    await api.createSession(lang);
    markSessionStarted();
    router.push(`/${lang}/new`);
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agreed) {
      setShowError(true);
      return;
    }
    await start.run();
  }

  const errorId = `${ids}-error`;
  return (
    <form onSubmit={submit} noValidate className="card space-y-5 px-4 sm:px-6">
      <div>
        <h2 id="consent-title" className="flex items-center gap-2 text-2xl font-bold text-ink">
          <ShieldIcon className="h-7 w-7 shrink-0 text-brand" />
          {t.consent.title}
        </h2>
        <p className="mt-2 text-muted">{t.consent.intro}</p>
      </div>
      <dl className="grid gap-4 sm:grid-cols-2">
        {t.consent.items.map((item) => (
          <div key={item.title} className="min-w-0 rounded-xl bg-canvas p-3 sm:p-4">
            <dt className="font-bold text-ink">{item.title}</dt>
            <dd className="mt-1 text-ink">{item.body}</dd>
          </div>
        ))}
      </dl>
      <p className="box-info">{t.consent.principles}</p>

      <div>
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border-2 border-line p-4 has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
          <input
            type="checkbox"
            className="mt-1 h-6 w-6 shrink-0 accent-brand"
            checked={agreed}
            onChange={(e) => {
              setAgreed(e.target.checked);
              if (e.target.checked) setShowError(false);
            }}
            aria-invalid={showError ? "true" : undefined}
            aria-describedby={showError ? errorId : undefined}
          />
          <span className="font-medium text-ink">{t.consent.agree}</span>
        </label>
        {showError && (
          <p id={errorId} role="alert" className="field-error">
            {t.consent.agreeRequired}
          </p>
        )}
      </div>

      {start.error !== null && <ErrorNotice error={start.error} onRetry={start.retry} />}

      <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={start.pending}>
        {start.pending ? t.landing.starting : t.landing.start}
        {!start.pending && <ArrowIcon />}
      </button>
    </form>
  );
}
