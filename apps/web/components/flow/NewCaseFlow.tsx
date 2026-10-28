"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { StepApplicant } from "./StepApplicant";
import { StepAuthority } from "./StepAuthority";
import { StepCheck } from "./StepCheck";
import { EMPTY_TRANSCRIPT, StepDescribe, type Transcript } from "./StepDescribe";
import { StepFile } from "./StepFile";
import { StepQuestions } from "./StepQuestions";
import { STEPS, Stepper, type StepKey } from "./Stepper";
import { api } from "@/lib/api";
import type { Authority, Case, IntakeResponse, Question, Rules } from "@/lib/types";
import { useAction } from "@/lib/use-action";

/** Where to pick up a saved draft. Status and fields come from the API; nothing is guessed. */
function resumeStep(c: Case): StepKey {
  if (!c.authority_name || !c.pio_address) return "authority";
  if (c.questions.length === 0 || c.questions.some((q) => !q.accepted)) return "questions";
  if (!c.has_applicant) return "applicant";
  return "check";
}

function mergeAuthorities(current: Authority[], incoming: Authority[]): Authority[] {
  const seen = new Set(current.map((a) => a.id));
  return [...current, ...incoming.filter((a) => !seen.has(a.id))];
}

/** The new-case flow (FR-1 to FR-6). The case id lives in `?case=` so a reload resumes it. */
export function NewCaseFlow() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const caseParam = useSearchParams().get("case");
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [step, setStep] = useState<StepKey>("describe");
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [transcript, setTranscript] = useState<Transcript>(EMPTY_TRANSCRIPT);
  const [authorities, setAuthorities] = useState<Authority[]>([]);
  const [rules, setRules] = useState<Rules | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const movedRef = useRef(false);
  const loader = useAction((id: string) => api.getCase(id));
  const runLoader = loader.run;

  useEffect(() => {
    if (!caseParam || caseData?.id === caseParam) return;
    runLoader(caseParam).then((loaded) => {
      if (!loaded) return;
      if (loaded.status !== "draft") {
        router.replace(`/${lang}/cases/${loaded.id}`);
        return;
      }
      setCaseData(loaded);
      setStep(resumeStep(loaded));
    });
  }, [caseParam, caseData?.id, lang, router, runLoader]);

  // Move focus to the new step's heading so screen reader and keyboard users land on it.
  useEffect(() => {
    if (!movedRef.current) return;
    headingRef.current?.focus();
  }, [step]);

  const goTo = useCallback((next: StepKey) => {
    movedRef.current = true;
    setStep(next);
    window.scrollTo({ top: 0 });
  }, []);
  const go = (offset: number) => goTo(STEPS[STEPS.indexOf(step) + offset] ?? step);

  function onCreated(created: Case) {
    setCaseData(created);
    // Keep the opaque case id in the URL (never any case content) so a reload resumes the draft.
    window.history.replaceState(null, "", `/${lang}/new?case=${created.id}`);
  }

  function onIntake(response: IntakeResponse) {
    setIntake(response);
    setAuthorities((current) => mergeAuthorities(current, response.authorities));
  }

  const onQuestionsChange = useCallback((update: (qs: Question[]) => Question[]) => {
    setCaseData((c) => (c ? { ...c, questions: update(c.questions) } : c));
  }, []);
  const onRules = useCallback((r: Rules) => setRules(r), []);

  const titles: Record<StepKey, string> = {
    describe: t.flow.describe.title,
    authority: t.flow.authority.title,
    questions: t.flow.questions.title,
    applicant: t.flow.applicant.title,
    check: t.flow.check.title,
    file: t.flow.file.title,
  };

  function body() {
    if (loader.pending && !caseData) {
      return (
        <p role="status" className="text-muted">
          {t.flow.loadingCase}
        </p>
      );
    }
    if (loader.error !== null && !caseData) {
      return <ErrorNotice error={loader.error} onRetry={loader.retry} />;
    }
    if (step === "describe" || !caseData) {
      return (
        <StepDescribe
          caseData={caseData}
          intake={intake}
          transcript={transcript}
          onTranscript={setTranscript}
          onCreated={onCreated}
          onIntake={onIntake}
          onNext={() => goTo("authority")}
        />
      );
    }
    switch (step) {
      case "authority":
        return (
          <StepAuthority
            caseData={caseData}
            candidates={authorities}
            jurisdictionHint={intake?.intake.jurisdiction_hint ?? null}
            onSaved={(updated) => {
              setCaseData(updated);
              goTo("questions");
            }}
            onBack={() => go(-1)}
          />
        );
      case "questions":
        return (
          <StepQuestions
            caseData={caseData}
            suggestions={intake?.intake.records_wanted ?? []}
            onQuestionsChange={onQuestionsChange}
            onNext={() => go(1)}
            onBack={() => go(-1)}
          />
        );
      case "applicant":
        return (
          <StepApplicant
            caseData={caseData}
            onSaved={() => setCaseData((c) => (c ? { ...c, has_applicant: true } : c))}
            onNext={() => go(1)}
            onBack={() => go(-1)}
          />
        );
      case "check":
        return (
          <StepCheck
            caseData={caseData}
            rules={rules}
            onRules={onRules}
            goTo={goTo}
            onNext={() => go(1)}
            onBack={() => go(-1)}
          />
        );
      case "file":
        return <StepFile caseData={caseData} rules={rules} onBack={() => go(-1)} />;
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">{t.flow.title}</h1>
      <Stepper current={step} />
      <section aria-labelledby="step-heading" className="mt-8">
        <h2
          id="step-heading"
          ref={headingRef}
          tabIndex={-1}
          className="mb-4 text-2xl font-bold text-ink focus:outline-none"
        >
          {titles[step]}
        </h2>
        {body()}
      </section>
    </div>
  );
}
