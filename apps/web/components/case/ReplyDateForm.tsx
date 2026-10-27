"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { api } from "@/lib/api";
import { todayInIndia } from "@/lib/i18n-core";
import type { Case } from "@/lib/types";
import { useAction } from "@/lib/use-action";

/** POST /reply without a photo: the user types the day the reply arrived. */
export function ReplyDateForm({ caseData, onUpdated }: { caseData: Case; onUpdated: (c: Case) => void }) {
  const { t } = useI18n();
  const c = t.caseDetail;
  const ids = useId();
  const [replyOn, setReplyOn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const reply = useAction((date: string) => api.recordReply(caseData.id, date));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!replyOn) {
      setError(c.replyRequired);
      return;
    }
    setError(null);
    const updated = await reply.run(replyOn);
    if (updated) {
      onUpdated(updated);
      setReplyOn("");
    }
  }

  return (
    <form onSubmit={submit} noValidate className="card space-y-3">
      <h3 className="text-lg font-bold text-ink">{c.replyTitle}</h3>
      <p className="text-muted">{c.replyManualHint}</p>
      <label htmlFor={`${ids}-reply`} className="field-label">
        {c.replyDate}
      </label>
      <input
        id={`${ids}-reply`}
        type="date"
        className="field-input"
        value={replyOn}
        min={caseData.filed_on ?? undefined}
        max={todayInIndia()}
        onChange={(e) => setReplyOn(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={error ? `${ids}-reply-error` : undefined}
      />
      {error && (
        <p id={`${ids}-reply-error`} role="alert" className="field-error">
          {error}
        </p>
      )}
      {reply.error !== null && <ErrorNotice error={reply.error} onRetry={reply.retry} />}
      <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={reply.pending}>
        {reply.pending ? c.replySaving : c.replySave}
      </button>
    </form>
  );
}
