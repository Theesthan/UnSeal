"use client";

import { useId, useState, type FormEvent } from "react";
import { useI18n } from "./I18nProvider";
import { CheckIcon, ShieldIcon } from "./icons";
import { format } from "@/lib/i18n-core";
import type { Question } from "@/lib/types";

export interface QuestionCardProps {
  question: Question;
  /** 1-based number shown to the user and used in every button's accessible name. */
  number: number;
  /** Language of the question text (the case language), which may differ from the UI. */
  contentLang: string;
  onAccept: () => Promise<void> | void;
  /** Resolve to false when saving failed, to keep the editor open with the user's text. */
  onSave: (text: string) => Promise<boolean | void> | boolean | void;
  onRemove?: () => Promise<void> | void;
  disabled?: boolean;
}

export function QuestionCard({
  question,
  number,
  contentLang,
  onAccept,
  onSave,
  onRemove,
  disabled = false,
}: QuestionCardProps) {
  const { t, lang } = useI18n();
  const q = t.question;
  const ids = useId();
  const headingId = `${ids}-heading`;
  const fieldId = `${ids}-field`;
  const errorId = `${ids}-error`;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(question.rewritten_text);
  const [error, setError] = useState<string | null>(null);
  const n = { n: number };
  // Mark the question text with its own language only when it differs from the page.
  const textLang = contentLang === lang ? undefined : contentLang;
  const hasRewrite = question.rewritten_text.trim() !== "";

  function startEditing() {
    setDraft(question.rewritten_text || question.original_text);
    setError(null);
    setEditing(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) {
      setError(q.emptyError);
      return;
    }
    const saved = await onSave(text);
    if (saved !== false) setEditing(false);
  }

  return (
    <article aria-labelledby={headingId} className="card min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={headingId} className="text-lg font-bold text-ink">
          {format(t.common.questionN, n)}
        </h3>
        {question.accepted && (
          <span className="badge bg-ok-soft text-ok">
            <CheckIcon />
            {q.accepted}
          </span>
        )}
      </div>

      <dl className="mt-4 space-y-4">
        <div>
          <dt className="text-sm font-semibold text-muted">{q.original}</dt>
          <dd lang={textLang} className="mt-1 break-words text-muted">
            {question.original_text}
          </dd>
        </div>
        {hasRewrite && (
          <div className="rounded-xl bg-brand-soft p-4">
            <dt className="text-sm font-semibold text-brand-strong">{q.rewritten}</dt>
            <dd lang={textLang} className="mt-1 break-words text-lg font-medium text-ink">
              {question.rewritten_text}
            </dd>
          </div>
        )}
        {question.records_requested.length > 0 && (
          <div>
            <dt className="text-sm font-semibold text-muted">{q.records}</dt>
            <dd className="mt-1">
              <ul lang={textLang} className="list-disc space-y-1 ps-5 break-words">
                {question.records_requested.map((record) => (
                  <li key={record}>{record}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        {question.reason && (
          <div>
            <dt className="text-sm font-semibold text-muted">{q.reason}</dt>
            <dd lang={textLang} className="mt-1 break-words">
              {question.reason}
            </dd>
          </div>
        )}
      </dl>

      {question.personal_information && (
        <div role="note" className="box-warn mt-4 space-y-2">
          <p className="flex gap-2 font-semibold">
            <ShieldIcon />
            <span>{q.personalWarning}</span>
          </p>
          {!hasRewrite && <p>{q.refused}</p>}
          {question.suggestion && (
            <>
              <p className="font-semibold">{q.suggestion}</p>
              <p lang={textLang} className="break-words">
                {question.suggestion}
              </p>
              <button
                type="button"
                className="btn btn-secondary w-full sm:w-auto"
                aria-label={format(q.useSuggestionLabel, n)}
                disabled={disabled}
                onClick={() => onSave(question.suggestion ?? "")}
              >
                {q.useSuggestion}
              </button>
            </>
          )}
        </div>
      )}

      {editing ? (
        <form className="mt-4" onSubmit={submit} noValidate>
          <label htmlFor={fieldId} className="field-label">
            {format(q.editField, n)}
          </label>
          <textarea
            id={fieldId}
            lang={textLang}
            className="field-input field-sizing-content min-h-32"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? errorId : undefined}
          />
          {error && (
            <p id={errorId} role="alert" className="field-error">
              {error}
            </p>
          )}
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <button
              type="submit"
              className="btn btn-primary"
              aria-label={format(q.saveLabel, n)}
              disabled={disabled}
            >
              {q.save}
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => setEditing(false)}>
              {q.cancel}
            </button>
          </div>
        </form>
      ) : (
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {!question.accepted && hasRewrite && (
            <button
              type="button"
              className="btn btn-primary"
              aria-label={format(q.acceptLabel, n)}
              disabled={disabled}
              onClick={() => onAccept()}
            >
              <CheckIcon />
              {q.accept}
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            aria-label={format(q.editLabel, n)}
            disabled={disabled}
            onClick={startEditing}
          >
            {q.edit}
          </button>
          {onRemove && (
            <button
              type="button"
              className="btn btn-quiet"
              aria-label={format(q.removeLabel, n)}
              disabled={disabled}
              onClick={() => onRemove()}
            >
              {q.remove}
            </button>
          )}
        </div>
      )}
    </article>
  );
}
