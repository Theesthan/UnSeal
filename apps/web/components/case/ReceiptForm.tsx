"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { CheckIcon } from "../icons";
import { api } from "@/lib/api";
import { todayInIndia } from "@/lib/i18n-core";
import type { Case } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface ReceiptFormProps {
  caseData: Case;
  onUpdated: (updated: Case) => void;
}

/**
 * PUT /cases/{id}/receipt: the day the office actually received the application (from the postal
 * tracking or the acknowledgement). The API restarts the deadlines from it; they stop being
 * estimates. Shown only while the case is reply_due.
 */
export function ReceiptForm({ caseData, onUpdated }: ReceiptFormProps) {
  const { t } = useI18n();
  const c = t.caseDetail;
  const ids = useId();
  const [date, setDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const save = useAction((receivedOn: string) => api.setReceipt(caseData.id, receivedOn));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!date) {
      setError(c.receiptRequired);
      return;
    }
    setError(null);
    const updated = await save.run(date);
    if (updated) {
      onUpdated(updated);
      setSaved(true);
      setDate("");
    }
  }

  return (
    <form onSubmit={submit} noValidate className="card space-y-3">
      <h3 className="text-lg font-bold text-ink">{c.receiptTitle}</h3>
      <p id={`${ids}-hint`} className="text-muted">
        {c.receiptHint}
      </p>
      <label htmlFor={`${ids}-date`} className="field-label">
        {c.receiptLabel}
      </label>
      <input
        id={`${ids}-date`}
        type="date"
        className="field-input"
        value={date}
        min={caseData.filed_on ?? undefined}
        max={todayInIndia()}
        onChange={(e) => setDate(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? `${ids}-hint ${ids}-error` : `${ids}-hint`}
      />
      {error && (
        <p id={`${ids}-error`} role="alert" className="field-error">
          {error}
        </p>
      )}
      {save.error !== null && <ErrorNotice error={save.error} onRetry={save.retry} />}
      {saved && (
        <p role="status" className="box-ok flex gap-2 font-semibold">
          <CheckIcon />
          <span>{c.receiptSaved}</span>
        </p>
      )}
      <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={save.pending}>
        {save.pending ? c.receiptSaving : c.receiptSave}
      </button>
    </form>
  );
}
