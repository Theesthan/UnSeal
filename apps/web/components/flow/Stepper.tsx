"use client";

import { useI18n } from "../I18nProvider";
import { CheckIcon } from "../icons";
import { format } from "@/lib/i18n-core";

export const STEPS = ["describe", "authority", "questions", "applicant", "check", "file"] as const;
export type StepKey = (typeof STEPS)[number];

export function Stepper({ current }: { current: StepKey }) {
  const { t } = useI18n();
  const index = STEPS.indexOf(current);
  const percent = Math.round(((index + 1) / STEPS.length) * 100);

  return (
    <div className="mt-4">
      <p className="font-semibold text-brand-strong">
        {format(t.flow.stepOf, { n: index + 1, total: STEPS.length })}:{" "}
        <span className="text-ink">{t.flow.steps[current]}</span>
      </p>
      <div
        role="progressbar"
        aria-label={t.flow.progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-line"
      >
        <div className="h-full rounded-full bg-brand" style={{ width: `${percent}%` }} />
      </div>
      <ol className="mt-4 hidden flex-wrap gap-2 md:flex">
        {STEPS.map((step, i) => {
          const state = i < index ? "done" : i === index ? "current" : "upcoming";
          return (
            <li
              key={step}
              aria-current={state === "current" ? "step" : undefined}
              className={`badge border ${
                state === "current"
                  ? "border-brand bg-brand text-white"
                  : state === "done"
                    ? "border-brand bg-brand-soft text-brand-strong"
                    : "border-line bg-surface text-muted"
              }`}
            >
              {state === "done" && <CheckIcon className="h-4 w-4" />}
              {i + 1}. {t.flow.steps[step]}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
