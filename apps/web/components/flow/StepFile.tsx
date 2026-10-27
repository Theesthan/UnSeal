"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { CheckIcon } from "../icons";
import { api } from "@/lib/api";
import { todayInIndia } from "@/lib/i18n-core";
import { FILING_MODES, type Case, type FilingBody, type Rules } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface StepFileProps {
  caseData: Case;
  rules: Rules | null;
  onBack: () => void;
}

/** FR-6 and FR-7: log the filing; the API computes every deadline from these dates. */
export function StepFile({ caseData, rules, onBack }: StepFileProps) {
  const { t, lang } = useI18n();
  const f = t.flow.file;
  const ids = useId();
  const router = useRouter();
  const today = todayInIndia();
  const modes = rules?.filing_channels.length ? rules.filing_channels : [...FILING_MODES];
  const [filedOn, setFiledOn] = useState(today);
  const [mode, setMode] = useState(modes.includes("post") ? "post" : modes[0]);
  const [receivedOn, setReceivedOn] = useState("");
  const [dateError, setDateError] = useState<string | null>(null);
  const channels = t.filingChannels as Record<string, string>;

  const save = useAction(async (body: FilingBody) => {
    const updated = await api.recordFiling(caseData.id, body);
    router.push(`/${lang}/cases/${updated.id}`);
    return updated;
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!filedOn) {
      setDateError(f.dateRequired);
      return;
    }
    setDateError(null);
    await save.run({ filed_on: filedOn, filing_mode: mode, received_on: receivedOn || null });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <p className="text-muted">{f.hint}</p>
      <div>
        <label htmlFor={`${ids}-filed`} className="field-label">
          {f.filedOn}
        </label>
        <input
          id={`${ids}-filed`}
          type="date"
          className="field-input"
          value={filedOn}
          max={today}
          onChange={(e) => setFiledOn(e.target.value)}
          aria-invalid={dateError ? "true" : undefined}
          aria-describedby={dateError ? `${ids}-filed-error` : undefined}
        />
        {dateError && (
          <p id={`${ids}-filed-error`} role="alert" className="field-error">
            {dateError}
          </p>
        )}
      </div>
      <fieldset>
        <legend className="field-label">{f.mode}</legend>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {modes.map((m) => (
            <label
              key={m}
              className="flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border-2 border-line bg-surface px-4 has-[:checked]:border-brand has-[:checked]:bg-brand-soft"
            >
              <input
                type="radio"
                name="filing-mode"
                value={m}
                checked={mode === m}
                onChange={() => setMode(m)}
                className="h-5 w-5 accent-brand"
              />
              {channels[m] ?? m}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor={`${ids}-received`} className="field-label">
          {f.receivedOn} <span className="font-normal text-muted">({t.common.optional})</span>
        </label>
        <p id={`${ids}-received-hint`} className="field-hint">
          {f.receivedHint}
        </p>
        <input
          id={`${ids}-received`}
          type="date"
          className="field-input"
          value={receivedOn}
          min={filedOn || undefined}
          max={today}
          onChange={(e) => setReceivedOn(e.target.value)}
          aria-describedby={`${ids}-received-hint`}
        />
      </div>
      {save.error !== null && <ErrorNotice error={save.error} onRetry={save.retry} />}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button type="button" className="btn btn-quiet" onClick={onBack}>
          {t.common.back}
        </button>
        <button type="submit" className="btn btn-primary" disabled={save.pending}>
          <CheckIcon />
          {save.pending ? f.saving : f.submit}
        </button>
      </div>
    </form>
  );
}
