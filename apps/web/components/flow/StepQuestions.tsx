"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon } from "../icons";
import { QuestionCard } from "../QuestionCard";
import { api } from "@/lib/api";
import { format } from "@/lib/i18n-core";
import type { Case, Question, QuestionPatch } from "@/lib/types";
import { useAction } from "@/lib/use-action";

type QuestionsUpdater = (questions: Question[]) => Question[];

interface StepQuestionsProps {
  caseData: Case;
  suggestions: string[];
  onQuestionsChange: (update: QuestionsUpdater) => void;
  onNext: () => void;
  onBack: () => void;
}

/** FR-2: each question is rewritten into a records request; the user accepts or edits each. */
export function StepQuestions({
  caseData,
  suggestions,
  onQuestionsChange,
  onNext,
  onBack,
}: StepQuestionsProps) {
  const { t } = useI18n();
  const s = t.flow.questions;
  const ids = useId();
  const [text, setText] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);

  const add = useAction(async (questionText: string) => {
    const created = await api.addQuestion(caseData.id, questionText);
    onQuestionsChange((qs) => [...qs, created]);
    return created;
  });
  const update = useAction(async (questionId: string, patch: QuestionPatch) => {
    const updated = await api.updateQuestion(caseData.id, questionId, patch);
    onQuestionsChange((qs) => qs.map((q) => (q.id === updated.id ? updated : q)));
    return true;
  });
  const remove = useAction(async (questionId: string) => {
    await api.deleteQuestion(caseData.id, questionId);
    onQuestionsChange((qs) => qs.filter((q) => q.id !== questionId));
    return true;
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim()) {
      setFieldError(s.required);
      return;
    }
    setFieldError(null);
    const created = await add.run(text.trim());
    if (created) setText("");
  }

  const questions = caseData.questions;
  const allAccepted = questions.length > 0 && questions.every((q) => q.accepted);
  const unusedSuggestions = suggestions.filter(
    (idea) => !questions.some((q) => q.original_text === idea),
  );
  const busy = update.pending || remove.pending;
  const listError = update.error ?? remove.error;
  const contentLang = caseData.language;
  const errorId = `${ids}-error`;
  const hintId = `${ids}-continue-hint`;

  return (
    <div className="space-y-6">
      <p className="text-muted">{s.hint}</p>

      <form onSubmit={submit} noValidate className="card space-y-3">
        <label htmlFor={`${ids}-new`} className="field-label">
          {s.addLabel}
        </label>
        <textarea
          id={`${ids}-new`}
          lang={contentLang}
          className="field-input field-sizing-content min-h-28"
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-invalid={fieldError ? "true" : undefined}
          aria-describedby={fieldError ? errorId : undefined}
        />
        {fieldError && (
          <p id={errorId} role="alert" className="field-error">
            {fieldError}
          </p>
        )}
        {unusedSuggestions.length > 0 && (
          <div>
            <p className="text-sm font-semibold text-muted">{s.suggestionsTitle}</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {unusedSuggestions.map((idea) => (
                <li key={idea} className="min-w-0">
                  <button
                    type="button"
                    lang={contentLang}
                    className="badge min-h-11 max-w-full border border-brand bg-surface text-start break-words text-brand-strong hover:bg-brand-soft"
                    aria-label={format(s.useSuggestion, { text: idea })}
                    onClick={() => setText(idea)}
                  >
                    + {idea}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {add.error !== null && <ErrorNotice error={add.error} onRetry={add.retry} />}
        <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={add.pending}>
          {add.pending ? s.adding : s.addButton}
        </button>
        {add.pending && (
          <p role="status" className="text-sm text-muted">
            {s.adding}
          </p>
        )}
      </form>

      {listError !== null && (
        <ErrorNotice error={listError} onRetry={update.error ? update.retry : remove.retry} />
      )}

      {questions.length === 0 ? (
        <p className="box-info">{s.empty}</p>
      ) : (
        <ol className="space-y-4" aria-label={s.title}>
          {questions.map((q, i) => (
            <li key={q.id}>
              <QuestionCard
                question={q}
                number={i + 1}
                contentLang={contentLang}
                disabled={busy}
                onAccept={() => update.run(q.id, { accepted: true }).then(() => undefined)}
                onSave={async (newText) =>
                  (await update.run(q.id, { rewritten_text: newText, accepted: true })) === true
                }
                onRemove={() => remove.run(q.id).then(() => undefined)}
              />
            </li>
          ))}
        </ol>
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" className="btn btn-quiet" onClick={onBack}>
          {t.common.back}
        </button>
        <div className="flex flex-col items-stretch gap-1 sm:items-end">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!allAccepted}
            aria-describedby={allAccepted ? undefined : hintId}
            onClick={onNext}
          >
            {t.common.continue}
            <ArrowIcon />
          </button>
          {!allAccepted && (
            <p id={hintId} className="text-sm text-muted">
              {s.acceptAll}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
