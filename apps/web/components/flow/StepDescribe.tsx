"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon, CheckIcon, ShieldIcon } from "../icons";
import { api } from "@/lib/api";
import { LANGUAGE_NAMES } from "@/lib/i18n-core";
import { buildIntakeMessage, type IntakeTurn } from "@/lib/intake-transcript";
import { LANGUAGES, type Case, type IntakeResponse, type Language } from "@/lib/types";
import { useAction } from "@/lib/use-action";

/** The intake conversation so far. The API keeps none of it, so the browser does. */
export interface Transcript {
  description: string;
  turns: IntakeTurn[];
}

export const EMPTY_TRANSCRIPT: Transcript = { description: "", turns: [] };

interface StepDescribeProps {
  caseData: Case | null;
  intake: IntakeResponse | null;
  transcript: Transcript;
  onTranscript: (transcript: Transcript) => void;
  onCreated: (created: Case) => void;
  onIntake: (response: IntakeResponse) => void;
  onNext: () => void;
}

const DESCRIPTION_MAX = 2000;
const ANSWER_MAX = 500;

/** FR-1: free-text concern, then the follow-up questions, each answered in its own field. */
export function StepDescribe({
  caseData,
  intake,
  transcript,
  onTranscript,
  onCreated,
  onIntake,
  onNext,
}: StepDescribeProps) {
  const { t, lang } = useI18n();
  const d = t.flow.describe;
  const f = t.flow.followUp;
  const ids = useId();
  const [concern, setConcern] = useState(transcript.description);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [appLang, setAppLang] = useState<Language>((caseData?.language as Language) ?? lang);
  const [fieldError, setFieldError] = useState<string | null>(null);

  // Each turn sends the whole conversation (docs/api.md: the server keeps no intake history).
  const send = useAction(async (next: Transcript) => {
    const current = caseData ?? (await api.createCase({ language: appLang }));
    if (!caseData) onCreated(current);
    const response = await api.intake(current.id, buildIntakeMessage(next.description, next.turns));
    onTranscript(next);
    onIntake(response);
    return response;
  });

  async function submitConcern(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!concern.trim()) {
      setFieldError(d.required);
      return;
    }
    setFieldError(null);
    await send.run({ description: concern.trim(), turns: [] });
  }

  async function submitAnswers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const questions = intake?.intake.follow_up_questions ?? [];
    const answered = questions
      .filter((q) => (answers[q] ?? "").trim() !== "")
      .map((q) => ({ question: q, answer: answers[q].trim() }));
    if (answered.length === 0) {
      setFieldError(f.required);
      return;
    }
    setFieldError(null);
    const response = await send.run({ ...transcript, turns: [...transcript.turns, ...answered] });
    if (response) setAnswers({});
  }

  const errorId = `${ids}-error`;
  const privacyId = `${ids}-privacy`;
  const contentLang = appLang === lang ? undefined : appLang;
  // Free text goes to the model. The API masks phone numbers and emails first, but it cannot spot
  // a name or an address, so the user is told not to type them (they go in the applicant step).
  const privacyNote = (
    <p id={privacyId} className="box-info flex gap-2 text-sm">
      <ShieldIcon className="mt-0.5 h-5 w-5 shrink-0" />
      <span>{t.flow.noPersonalDetails}</span>
    </p>
  );
  const describedBy = (withError: boolean) => [privacyId, withError ? errorId : null].filter(Boolean).join(" ");

  if (!intake) {
    return (
      <form onSubmit={submitConcern} noValidate className="space-y-5">
        <p className="text-muted">{d.hint}</p>
        <fieldset>
          <legend className="field-label">{d.languageLabel}</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {LANGUAGES.map((l) => (
              <label
                key={l}
                lang={l}
                className="flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border-2 border-line bg-surface px-4 has-[:checked]:border-brand has-[:checked]:bg-brand-soft"
              >
                <input
                  type="radio"
                  name="application-language"
                  value={l}
                  checked={appLang === l}
                  disabled={Boolean(caseData)}
                  onChange={() => setAppLang(l)}
                  className="h-5 w-5 accent-brand"
                />
                {LANGUAGE_NAMES[l]}
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor={`${ids}-concern`} className="field-label">
            {d.label}
          </label>
          <div className="mt-2">{privacyNote}</div>
          <textarea
            id={`${ids}-concern`}
            lang={contentLang}
            className="field-input field-sizing-content min-h-40"
            placeholder={d.placeholder}
            maxLength={DESCRIPTION_MAX}
            value={concern}
            onChange={(e) => setConcern(e.target.value)}
            aria-invalid={fieldError ? "true" : undefined}
            aria-describedby={describedBy(Boolean(fieldError))}
          />
          {fieldError && (
            <p id={errorId} role="alert" className="field-error">
              {fieldError}
            </p>
          )}
        </div>
        {send.error !== null && <ErrorNotice error={send.error} onRetry={send.retry} />}
        <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={send.pending}>
          {send.pending ? d.sending : d.submit}
          {!send.pending && <ArrowIcon />}
        </button>
      </form>
    );
  }

  const followUps = intake.intake.follow_up_questions;
  const ready = intake.intake.ready_to_draft;

  return (
    <div className="space-y-5">
      {ready && (
        <p role="status" className="box-ok flex items-center gap-2 font-semibold">
          <CheckIcon />
          {f.ready}
        </p>
      )}
      {!ready && followUps.length > 0 && (
        <form onSubmit={submitAnswers} noValidate className="card space-y-4">
          <fieldset aria-describedby={`${ids}-hint${fieldError ? ` ${errorId}` : ""}`} className="space-y-4">
            <legend className="text-xl font-bold text-ink">{f.title}</legend>
            <p id={`${ids}-hint`} className="text-muted">
              {f.hint}
            </p>
            {privacyNote}
            {followUps.map((question, i) => (
              <div key={question}>
                <label htmlFor={`${ids}-answer-${i}`} lang={contentLang} className="field-label break-words">
                  {question}
                </label>
                <textarea
                  id={`${ids}-answer-${i}`}
                  lang={contentLang}
                  className="field-input field-sizing-content min-h-20"
                  maxLength={ANSWER_MAX}
                  value={answers[question] ?? ""}
                  onChange={(e) => setAnswers((current) => ({ ...current, [question]: e.target.value }))}
                  aria-describedby={privacyId}
                />
              </div>
            ))}
            {fieldError && (
              <p id={errorId} role="alert" className="field-error">
                {fieldError}
              </p>
            )}
          </fieldset>
          {send.error !== null && <ErrorNotice error={send.error} onRetry={send.retry} />}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <button type="submit" className="btn btn-primary" disabled={send.pending}>
              {send.pending ? f.sending : f.send}
            </button>
            <button type="button" className="btn btn-quiet" onClick={onNext}>
              {f.skip}
            </button>
          </div>
        </form>
      )}
      {(ready || followUps.length === 0) && (
        <button type="button" className="btn btn-primary w-full sm:w-auto" onClick={onNext}>
          {t.common.continue}
          <ArrowIcon />
        </button>
      )}
    </div>
  );
}
