"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { CheckIcon, ShieldIcon } from "../icons";
import { api } from "@/lib/api";
import { format, formatDate, todayInIndia } from "@/lib/i18n-core";
import { REPLY_ACCEPT, REPLY_MAX_MB, REPLY_MAX_PAGES, replyFileProblem } from "@/lib/reply-limits";
import type { Case, ReplyReading } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface ReplyReaderProps {
  caseData: Case;
  onCaseUpdated: (updated: Case) => void;
  /** The reader's suggested appeal grounds, once the reply is recorded (or already was). */
  onGrounds: (grounds: string[]) => void;
}

const STATUS_TONE: Record<string, string> = {
  given: "bg-ok-soft text-ok",
  refused: "bg-danger-soft text-danger",
  partial: "bg-sun-soft text-sun-ink border border-[#e8c46a]",
  transferred: "bg-brand-soft text-brand-strong",
};

/**
 * FR-11: read a photo or PDF of the PIO's reply. The file goes to the API only after the user
 * ticks the consent box; the API sends it to the model to read and stores nothing. The letter's
 * date is only a default: the user confirms the day it arrived, which POST /reply records.
 */
export function ReplyReader({ caseData, onCaseUpdated, onGrounds }: ReplyReaderProps) {
  const { t, lang } = useI18n();
  const r = t.replyReader;
  const ids = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [consent, setConsent] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [reading, setReading] = useState<ReplyReading | null>(null);
  const [receivedOn, setReceivedOn] = useState("");
  const [dateError, setDateError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const needsDate = caseData.status === "reply_due" || caseData.status === "deemed_refused";
  const limits = { mb: REPLY_MAX_MB, pages: REPLY_MAX_PAGES };
  const statuses = r.statuses as Record<string, string>;

  const read = useAction((file: File) => api.readReply(caseData.id, file));
  const record = useAction((date: string) => api.recordReply(caseData.id, date));

  async function submitFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!consent) return setProblem(t.errors.consent_required);
    if (!file) return setProblem(r.fileRequired);
    const local = replyFileProblem(file);
    if (local) return setProblem(format(t.errors[local], limits));
    setProblem(null);
    setDone(false);
    const result = await read.run(file);
    if (!result) return;
    setReading(result);
    setReceivedOn(result.letter_date ?? "");
    if (!needsDate) {
      onGrounds(result.suggested_grounds);
      setDone(true);
    }
  }

  async function submitDate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!receivedOn) return setDateError(r.receivedRequired);
    setDateError(null);
    const updated = await record.run(receivedOn);
    if (updated && reading) {
      onCaseUpdated(updated);
      onGrounds(reading.suggested_grounds);
      setDone(true);
    }
  }

  return (
    <section aria-labelledby={`${ids}-title`} className="card space-y-4">
      <h3 id={`${ids}-title`} className="text-lg font-bold text-ink">
        {r.title}
      </h3>
      <p className="text-muted">{r.intro}</p>

      <form onSubmit={submitFile} noValidate className="space-y-4">
        <div>
          <label htmlFor={`${ids}-file`} className="field-label">
            {r.fileLabel}
          </label>
          <p id={`${ids}-file-hint`} className="field-hint">
            {format(r.fileHint, limits)}
          </p>
          <input
            ref={fileRef}
            id={`${ids}-file`}
            type="file"
            accept={REPLY_ACCEPT}
            aria-describedby={`${ids}-file-hint`}
            className="mt-2 block w-full min-w-0 text-base file:me-3 file:min-h-11 file:rounded-xl file:border-2 file:border-brand file:bg-surface file:px-4 file:font-semibold file:text-brand"
            onChange={() => setProblem(null)}
          />
        </div>
        <div className="flex items-start gap-3 rounded-xl border-2 border-line p-3 has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
          <input
            id={`${ids}-consent`}
            type="checkbox"
            className="mt-1 h-5 w-5 shrink-0 accent-brand"
            checked={consent}
            onChange={(e) => {
              setConsent(e.target.checked);
              if (e.target.checked) setProblem(null);
            }}
          />
          <label htmlFor={`${ids}-consent`} className="flex cursor-pointer gap-2 font-medium text-ink">
            <ShieldIcon className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <span>{r.consent}</span>
          </label>
        </div>
        {problem && (
          <p role="alert" className="field-error">
            {problem}
          </p>
        )}
        {read.error !== null && <ErrorNotice error={read.error} onRetry={read.retry} />}
        <button type="submit" className="btn btn-secondary w-full sm:w-auto" disabled={read.pending}>
          {read.pending ? r.reading : r.read}
        </button>
      </form>

      {reading && (
        <div className="space-y-4 border-t border-line pt-4">
          <h4 className="text-lg font-bold text-ink">{r.resultTitle}</h4>
          <p className="box-info text-sm">{r.checkNote}</p>
          <dl className="grid gap-1 sm:grid-cols-[auto_1fr] sm:gap-x-4">
            <dt className="font-semibold text-muted">{r.letterDate}</dt>
            <dd>
              {reading.letter_date ? (
                <time dateTime={reading.letter_date}>{formatDate(reading.letter_date, lang)}</time>
              ) : (
                r.letterDateUnknown
              )}
            </dd>
          </dl>
          {reading.items.length > 0 ? (
            <ul aria-label={r.points} className="space-y-2">
              {reading.items.map((item) => (
                <li
                  key={item.number}
                  className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface p-3"
                >
                  <span className="font-semibold text-ink">{format(r.point, { n: item.number })}</span>
                  <span className={`badge ${STATUS_TONE[item.status] ?? "bg-canvas text-ink border border-line"}`}>
                    {statuses[item.status] ?? statuses.unclear}
                  </span>
                  {item.section_cited && (
                    <span className="text-sm text-muted">
                      {format(r.sectionCited, { section: item.section_cited })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p>{r.noPoints}</p>
          )}
          <p className={reading.fee_demanded ? "font-semibold text-danger" : "text-muted"}>
            {reading.fee_demanded ? r.feeDemanded : r.noFee}
          </p>
          {reading.transferred_to && (
            <p className="break-words">{format(r.transferredTo, { office: reading.transferred_to })}</p>
          )}

          {needsDate && !done && (
            <form onSubmit={submitDate} noValidate className="space-y-3">
              <h4 className="text-lg font-bold text-ink">{r.receivedTitle}</h4>
              <p id={`${ids}-date-hint`} className="text-muted">
                {r.receivedHint}
              </p>
              <label htmlFor={`${ids}-date`} className="field-label">
                {r.receivedLabel}
              </label>
              <input
                id={`${ids}-date`}
                type="date"
                className="field-input"
                value={receivedOn}
                min={caseData.filed_on ?? undefined}
                max={todayInIndia()}
                onChange={(e) => setReceivedOn(e.target.value)}
                aria-invalid={dateError ? "true" : undefined}
                aria-describedby={dateError ? `${ids}-date-hint ${ids}-date-error` : `${ids}-date-hint`}
              />
              {dateError && (
                <p id={`${ids}-date-error`} role="alert" className="field-error">
                  {dateError}
                </p>
              )}
              {record.error !== null && <ErrorNotice error={record.error} onRetry={record.retry} />}
              <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={record.pending}>
                {record.pending ? r.saving : r.save}
              </button>
            </form>
          )}
          {done && (
            <p role="status" className="box-ok flex gap-2 font-semibold">
              <CheckIcon />
              <span>{r.appealNext}</span>
            </p>
          )}
        </div>
      )}
    </section>
  );
}
