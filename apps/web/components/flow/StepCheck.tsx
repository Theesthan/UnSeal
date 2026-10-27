"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { FilingChecklist } from "../FilingChecklist";
import { FlagList } from "../FlagList";
import { useI18n } from "../I18nProvider";
import { ArrowIcon, CheckIcon, DownloadIcon } from "../icons";
import type { StepKey } from "./Stepper";
import { api, BlockedError } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { JURISDICTIONS, type Case, type Jurisdiction, type Rules, type ValidationFlag } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface StepCheckProps {
  caseData: Case;
  rules: Rules | null;
  onRules: (rules: Rules) => void;
  goTo: (step: StepKey) => void;
  onNext: () => void;
  onBack: () => void;
}

const FIX_STEP: Record<string, StepKey> = {
  missing_pio_address: "authority",
  missing_applicant_address: "applicant",
  no_questions: "questions",
};

/** FR-3 and FR-5: flags before export (blocking flags disable the download), then the PDF. */
export function StepCheck({ caseData, rules, onRules, goTo, onNext, onBack }: StepCheckProps) {
  const { t } = useI18n();
  const c = t.flow.check;
  const ids = useId();
  const [flags, setFlags] = useState<ValidationFlag[] | null>(null);
  const [paymentMode, setPaymentMode] = useState("");
  const [place, setPlace] = useState("");
  const [placeError, setPlaceError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  const jurisdiction = (JURISDICTIONS as readonly string[]).includes(caseData.jurisdiction ?? "")
    ? (caseData.jurisdiction as Jurisdiction)
    : null;

  const validation = useAction(() => api.getValidation(caseData.id));
  const loadRules = useAction((j: Jurisdiction) => api.getRules(j));
  const download = useAction(async (body: { payment_mode: string; place: string }) => {
    const pdf = await api.downloadApplication(caseData.id, body);
    saveBlob(pdf, "unseal-application.pdf");
    return true;
  });

  const runValidation = validation.run;
  const runLoadRules = loadRules.run;
  useEffect(() => {
    runValidation().then((v) => {
      if (v) setFlags(v.flags);
    });
  }, [caseData.id, runValidation]);
  useEffect(() => {
    if (!jurisdiction || rules) return;
    runLoadRules(jurisdiction).then((r) => {
      if (r) onRules(r);
    });
  }, [jurisdiction, rules, onRules, runLoadRules]);

  // A 409 from the API carries the blocking flags: they replace the list until the next check.
  const blockedError = download.error instanceof BlockedError ? download.error : null;
  const shownFlags = blockedError && blockedError.flags.length > 0 ? blockedError.flags : flags;
  const blocked = Boolean(shownFlags?.some((f) => f.severity === "block"));
  const selectedMode = paymentMode || rules?.payment_modes[0] || "";
  const modeLabels = t.paymentModes as Record<string, string>;
  const fixSteps = [
    ...new Set((shownFlags ?? []).map((f) => FIX_STEP[f.code]).filter((s): s is StepKey => Boolean(s))),
  ];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!place.trim()) {
      setPlaceError(c.placeRequired);
      return;
    }
    setPlaceError(null);
    setDownloaded(false);
    const ok = await download.run({ payment_mode: selectedMode, place: place.trim() });
    if (ok) setDownloaded(true);
  }

  const fixLabel: Record<StepKey, string> = {
    describe: t.flow.steps.describe,
    authority: c.editAuthority,
    questions: c.editQuestions,
    applicant: c.editApplicant,
    check: c.title,
    file: t.flow.steps.file,
  };

  return (
    <div className="space-y-6">
      <section aria-labelledby={`${ids}-flags`} className="space-y-3">
        <h3 id={`${ids}-flags`} className="text-xl font-bold text-ink">
          {t.flags.title}
        </h3>
        {validation.pending && shownFlags === null && (
          <p role="status" className="text-muted">
            {c.checking}
          </p>
        )}
        {validation.error !== null && (
          <ErrorNotice error={validation.error} onRetry={validation.retry} />
        )}
        {shownFlags !== null && <FlagList flags={shownFlags} />}
        {blocked && <p className="font-semibold text-danger">{c.blockedNote}</p>}
        {fixSteps.length > 0 && (
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {fixSteps.map((step) => (
              <button key={step} type="button" className="btn btn-secondary" onClick={() => goTo(step)}>
                {fixLabel[step]}
              </button>
            ))}
          </div>
        )}
      </section>

      <form onSubmit={submit} noValidate className="card space-y-4">
        {loadRules.error !== null && <ErrorNotice error={loadRules.error} onRetry={loadRules.retry} />}
        {rules === null && loadRules.pending && (
          <p role="status" className="text-muted">
            {t.checklist.loading}
          </p>
        )}
        {rules && (
          <div>
            <label htmlFor={`${ids}-mode`} className="field-label">
              {c.paymentModeLabel}
            </label>
            <select
              id={`${ids}-mode`}
              className="field-input"
              value={selectedMode}
              onChange={(e) => setPaymentMode(e.target.value)}
            >
              {rules.payment_modes.map((m) => (
                <option key={m} value={m}>
                  {modeLabels[m] ?? m}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label htmlFor={`${ids}-place`} className="field-label">
            {c.placeLabel}
          </label>
          <input
            id={`${ids}-place`}
            className="field-input"
            value={place}
            onChange={(e) => setPlace(e.target.value)}
            aria-invalid={placeError ? "true" : undefined}
            aria-describedby={placeError ? `${ids}-place-error` : undefined}
          />
          {placeError && (
            <p id={`${ids}-place-error`} role="alert" className="field-error">
              {placeError}
            </p>
          )}
        </div>
        {download.error !== null && (
          <ErrorNotice error={download.error} onRetry={download.retry} />
        )}
        {downloaded && (
          <p role="status" className="box-ok flex gap-2 font-semibold">
            <CheckIcon />
            <span>{c.downloaded}</span>
          </p>
        )}
        <button
          type="submit"
          className="btn btn-primary w-full sm:w-auto"
          disabled={blocked || download.pending || !rules}
          aria-describedby={blocked ? `${ids}-blocked` : undefined}
        >
          <DownloadIcon />
          {download.pending ? c.downloading : c.download}
        </button>
        {blocked && (
          <p id={`${ids}-blocked`} className="sr-only">
            {c.blockedNote}
          </p>
        )}
      </form>

      {rules && (
        <FilingChecklist
          rules={rules}
          authorityName={caseData.authority_name}
          pioAddress={caseData.pio_address}
          contentLang={caseData.language}
        />
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button type="button" className="btn btn-quiet" onClick={onBack}>
          {t.common.back}
        </button>
        <button type="button" className="btn btn-primary" onClick={onNext} disabled={blocked}>
          {c.next}
          <ArrowIcon />
        </button>
      </div>
    </div>
  );
}
