"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { CheckIcon, DownloadIcon } from "../icons";
import { api } from "@/lib/api";
import { appealState, initialGrounds, type Ground } from "@/lib/appeal";
import { saveBlob } from "@/lib/download";
import { format, formatDate, todayInIndia } from "@/lib/i18n-core";
import type { AppealBody, AppealFilingBody, Case } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface AppealPanelProps {
  caseData: Case;
  /** Grounds the reply reader suggested; null when the letter was not read. */
  suggestedGrounds: string[] | null;
  onCaseUpdated: (updated: Case) => void;
  /** Today in India (YYYY-MM-DD); injectable for tests. */
  today?: string;
}

type FieldKey = "grounds" | "address" | "confirm" | "delay" | "filedOn";

/**
 * FR-10: the first appeal (S. 19(1)). The PDF is built by the API from template text, the case's
 * dates and the grounds ticked here; the user's own words go in `details` and `delay_reason`.
 * The appeal goes to the First Appellate Authority of the same office: its name is printed from
 * the case, and the address (prefilled with the PIO's, the usual case) must be checked.
 */
export function AppealPanel({ caseData, suggestedGrounds, onCaseUpdated, today = todayInIndia() }: AppealPanelProps) {
  const { t, lang } = useI18n();
  const a = t.appeal;
  const ids = useId();
  const state = appealState(caseData, today);
  const [grounds, setGrounds] = useState<Ground[]>(() => initialGrounds(state.grounds, suggestedGrounds));
  const [address, setAddress] = useState(caseData.pio_address ?? "");
  const [confirmed, setConfirmed] = useState(false);
  const [details, setDetails] = useState("");
  const [delay, setDelay] = useState("");
  const [place, setPlace] = useState("");
  const [filedOn, setFiledOn] = useState(today);
  const [receivedOn, setReceivedOn] = useState("");
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [downloaded, setDownloaded] = useState(false);

  const download = useAction(async (body: AppealBody) => {
    saveBlob(await api.downloadAppeal(caseData.id, body), "unseal-first-appeal.pdf");
    return true;
  });
  const file = useAction((body: AppealFilingBody) => api.recordAppealFiling(caseData.id, body));

  const shownGrounds = grounds.filter((g) => state.grounds.includes(g));
  const groundLabels = a.grounds as Record<Ground, string>;

  function toggle(ground: Ground, on: boolean) {
    setGrounds((current) => (on ? [...current, ground] : current.filter((g) => g !== ground)));
  }

  async function submitAppeal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Partial<Record<FieldKey, string>> = {};
    if (shownGrounds.length === 0) next.grounds = a.groundsRequired;
    else if (!address.trim()) next.address = a.faaRequired;
    else if (!confirmed) next.confirm = a.faaConfirmRequired;
    else if (state.late && !delay.trim()) next.delay = a.delayRequired;
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setDownloaded(false);
    const ok = await download.run({
      // In the order the Act's grounds are listed, whatever order they were ticked in.
      grounds: state.grounds.filter((g) => shownGrounds.includes(g)),
      faa_address: address.trim(),
      details: details.trim(),
      delay_reason: state.late ? delay.trim() : "",
      place: place.trim(),
    });
    if (ok) setDownloaded(true);
  }

  async function submitFiling(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!filedOn) {
      setErrors({ filedOn: a.dateRequired });
      return;
    }
    setErrors({});
    const updated = await file.run({ filed_on: filedOn, received_on: receivedOn || null });
    if (updated) onCaseUpdated(updated);
  }

  const err = (key: FieldKey) =>
    errors[key] ? (
      <p id={`${ids}-${key}-error`} role="alert" className="field-error">
        {errors[key]}
      </p>
    ) : null;
  const described = (key: FieldKey, hint?: string) =>
    [hint, errors[key] ? `${ids}-${key}-error` : undefined].filter(Boolean).join(" ") || undefined;

  return (
    <section id="first-appeal" aria-labelledby={`${ids}-title`} className="card space-y-5">
      <div>
        <h3 id={`${ids}-title`} tabIndex={-1} className="text-xl font-bold text-ink focus:outline-none">
          {a.title}
        </h3>
        <p className="mt-1 text-muted">{a.intro}</p>
      </div>

      {caseData.appeal_filed_on && (
        <p className="box-info">
          {format(a.filedNote, { date: formatDate(caseData.appeal_filed_on, lang) })}
        </p>
      )}

      <form onSubmit={submitAppeal} noValidate className="space-y-5">
        <fieldset aria-describedby={described("grounds", `${ids}-grounds-hint`)}>
          <legend className="field-label">{a.groundsLegend}</legend>
          <p id={`${ids}-grounds-hint`} className="field-hint">
            {suggestedGrounds ? a.suggestedNote : a.groundsHint}
          </p>
          <div className="mt-2 space-y-2">
            {state.grounds.map((g) => (
              <div
                key={g}
                className="flex items-start gap-3 rounded-xl border-2 border-line p-3 has-[:checked]:border-brand has-[:checked]:bg-brand-soft"
              >
                <input
                  id={`${ids}-ground-${g}`}
                  type="checkbox"
                  className="mt-1 h-5 w-5 shrink-0 accent-brand"
                  checked={shownGrounds.includes(g)}
                  onChange={(e) => toggle(g, e.target.checked)}
                />
                <label htmlFor={`${ids}-ground-${g}`} className="cursor-pointer font-medium text-ink">
                  {groundLabels[g]}
                </label>
              </div>
            ))}
          </div>
          {err("grounds")}
        </fieldset>

        <div className="space-y-2">
          <p className="text-sm font-semibold text-muted">{a.addressedTo}</p>
          <p lang={caseData.language} className="font-bold break-words text-ink">
            <span lang={lang}>{a.faaTitle}</span>
            {caseData.authority_name ? `, ${caseData.authority_name}` : ""}
          </p>
          <label htmlFor={`${ids}-address`} className="field-label">
            {a.faaLabel}
          </label>
          <p id={`${ids}-address-hint`} className="field-hint">
            {a.faaHint}
          </p>
          <textarea
            id={`${ids}-address`}
            lang={caseData.language}
            className="field-input field-sizing-content min-h-28"
            maxLength={1000}
            value={address}
            onChange={(e) => {
              setAddress(e.target.value);
              setConfirmed(false);
            }}
            aria-invalid={errors.address ? "true" : undefined}
            aria-describedby={described("address", `${ids}-address-hint`)}
          />
          {err("address")}
          <div className="flex items-start gap-3">
            <input
              id={`${ids}-confirm`}
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0 accent-brand"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              aria-invalid={errors.confirm ? "true" : undefined}
              aria-describedby={described("confirm")}
            />
            <label htmlFor={`${ids}-confirm`} className="cursor-pointer font-medium text-ink">
              {a.faaConfirm}
            </label>
          </div>
          {err("confirm")}
        </div>

        <div>
          <label htmlFor={`${ids}-details`} className="field-label">
            {a.detailsLabel}
          </label>
          <p id={`${ids}-details-hint`} className="field-hint">
            {a.detailsHint}
          </p>
          <textarea
            id={`${ids}-details`}
            className="field-input field-sizing-content min-h-28"
            maxLength={2000}
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            aria-describedby={`${ids}-details-hint`}
          />
        </div>

        {state.late && (
          <div>
            <label htmlFor={`${ids}-delay`} className="field-label">
              {a.delayLabel}
            </label>
            <p id={`${ids}-delay-hint`} className="field-hint">
              {a.delayHint}
            </p>
            <textarea
              id={`${ids}-delay`}
              className="field-input field-sizing-content min-h-24"
              maxLength={1000}
              value={delay}
              onChange={(e) => setDelay(e.target.value)}
              aria-invalid={errors.delay ? "true" : undefined}
              aria-describedby={described("delay", `${ids}-delay-hint`)}
            />
            {err("delay")}
          </div>
        )}

        <div>
          <label htmlFor={`${ids}-place`} className="field-label">
            {t.flow.check.placeLabel}
          </label>
          <input
            id={`${ids}-place`}
            className="field-input"
            maxLength={100}
            value={place}
            onChange={(e) => setPlace(e.target.value)}
          />
        </div>

        {download.error !== null && <ErrorNotice error={download.error} onRetry={download.retry} />}
        {downloaded && (
          <p role="status" className="box-ok flex gap-2 font-semibold">
            <CheckIcon />
            <span>{a.downloaded}</span>
          </p>
        )}
        <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={download.pending}>
          <DownloadIcon />
          {download.pending ? a.downloading : a.download}
        </button>
      </form>

      {state.canFile && (
        <form onSubmit={submitFiling} noValidate className="space-y-3 border-t border-line pt-5">
          <h4 className="text-lg font-bold text-ink">{a.filingTitle}</h4>
          <div>
            <label htmlFor={`${ids}-filed`} className="field-label">
              {a.filedOn}
            </label>
            <input
              id={`${ids}-filed`}
              type="date"
              className="field-input"
              value={filedOn}
              max={today}
              onChange={(e) => setFiledOn(e.target.value)}
              aria-invalid={errors.filedOn ? "true" : undefined}
              aria-describedby={described("filedOn")}
            />
            {err("filedOn")}
          </div>
          <div>
            <label htmlFor={`${ids}-received`} className="field-label">
              {a.receivedOn} <span className="font-normal text-muted">({t.common.optional})</span>
            </label>
            <p id={`${ids}-received-hint`} className="field-hint">
              {a.receivedHint}
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
          {file.error !== null && <ErrorNotice error={file.error} onRetry={file.retry} />}
          <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={file.pending}>
            <CheckIcon />
            {file.pending ? a.filing : a.fileSubmit}
          </button>
        </form>
      )}
    </section>
  );
}
