"use client";

import { Fragment, type ReactNode } from "react";
import { useI18n } from "./I18nProvider";
import { CheckIcon, ClockIcon } from "./icons";
import { format, formatDate, formatDateTime } from "@/lib/i18n-core";
import { buildTimeline, type StageState, type TimelineEntry } from "@/lib/timeline";
import type { Case } from "@/lib/types";
import type { Messages } from "@/messages/types";

export interface TimelineProps {
  caseData: Pick<
    Case,
    "status" | "filed_on" | "received_on" | "received_estimated" | "deadlines"
  > &
    Partial<Case>;
}

const MARKER: Record<StageState, string> = {
  done: "border-brand bg-brand text-white",
  current: "border-sun bg-sun text-ink ring-4 ring-sun-soft",
  upcoming: "border-line bg-surface text-muted",
};

const STATE_BADGE: Record<StageState, string> = {
  done: "bg-brand-soft text-brand-strong",
  current: "bg-sun text-ink",
  upcoming: "bg-canvas text-muted border border-line",
};

/** Put a React node where `{slot}` sits in a translated template (word order differs by language). */
function withSlot(template: string, slot: string, node: ReactNode): ReactNode {
  const [before, after = ""] = template.split(`{${slot}}`);
  return (
    <>
      {before}
      {node}
      {after}
    </>
  );
}

function EntryDate({ entry, lang }: { entry: TimelineEntry; lang: Parameters<typeof formatDate>[1] }) {
  if (entry.at) {
    return <time dateTime={entry.at}>{formatDateTime(entry.at, lang)}</time>;
  }
  if (entry.date) {
    return <time dateTime={entry.date}>{formatDate(entry.date, lang)}</time>;
  }
  return null;
}

function EstimatedTag({ t }: { t: Messages }) {
  return (
    <span className="badge ms-2 bg-sun-soft text-sun-ink border border-[#e8c46a] align-middle">
      <ClockIcon className="h-4 w-4 shrink-0" />
      {t.common.estimated}
    </span>
  );
}

/** Vertical timeline of statuses and deadlines (FR-7). Dates come only from the API. */
export function Timeline({ caseData }: TimelineProps) {
  const { t, lang } = useI18n();
  const model = buildTimeline({
    id: "",
    language: lang,
    jurisdiction: null,
    authority_name: null,
    pio_address: null,
    has_applicant: false,
    via_apio: false,
    third_party: false,
    life_liberty: false,
    filing_mode: null,
    reply_received_on: null,
    appeal_filed_on: null,
    questions: [],
    created_at: "",
    ...caseData,
  });
  const statuses = t.timeline.statuses as Record<string, string>;
  const descriptions = t.timeline.descriptions as Record<string, string>;
  const deadlineLabels = t.timeline.deadlines as Record<string, string>;

  function entryLabel(entry: TimelineEntry): ReactNode {
    const date = <EntryDate entry={entry} lang={lang} />;
    if (entry.kind === "filed_on") return <p>{withSlot(t.timeline.filedOn, "date", date)}</p>;
    if (entry.kind === "reply_received_on") {
      return <p>{withSlot(t.timeline.replyReceivedOn, "date", date)}</p>;
    }
    if (entry.kind === "appeal_filed_on") {
      return <p>{withSlot(t.timeline.appealFiledOn, "date", date)}</p>;
    }
    if (entry.kind === "received_on") {
      return (
        <p>
          {withSlot(t.timeline.receivedOn, "date", date)}
          {entry.estimated && <EstimatedTag t={t} />}
        </p>
      );
    }
    const kind = entry.deadlineKind ?? "";
    return (
      <>
        <p className="text-sm font-semibold text-muted">
          {deadlineLabels[kind] ?? format(t.timeline.unknownDeadline, { kind })}
        </p>
        <p className="text-lg font-bold text-ink">
          {date}
          {entry.estimated && <EstimatedTag t={t} />}
        </p>
      </>
    );
  }

  return (
    <div className="min-w-0">
      {model.unknownStatus !== null && (
        <p role="status" className="box-warn mb-4">
          {format(t.timeline.unknownStatus, { status: model.unknownStatus })}
        </p>
      )}
      <ol aria-label={t.timeline.title} className="relative">
        {model.stages.map((stage, index) => {
          const last = index === model.stages.length - 1;
          return (
            <li
              key={stage.key}
              aria-current={stage.state === "current" ? "step" : undefined}
              className="relative flex gap-4 pb-6 last:pb-0"
            >
              {!last && (
                <span
                  aria-hidden="true"
                  className={`absolute start-[1.1rem] top-10 bottom-0 w-0.5 ${
                    stage.state === "done" ? "bg-brand" : "bg-line"
                  }`}
                />
              )}
              <span
                aria-hidden="true"
                className={`relative z-10 mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-sm font-bold ${MARKER[stage.state]}`}
              >
                {stage.state === "done" ? <CheckIcon className="h-5 w-5" /> : index + 1}
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-bold break-words text-ink">
                    {statuses[stage.status] ?? stage.status}
                  </h3>
                  <span className={`badge ${STATE_BADGE[stage.state]}`}>
                    {t.timeline.stateLabels[stage.state]}
                  </span>
                </div>
                <p className="mt-1 break-words text-muted">{descriptions[stage.status] ?? ""}</p>
                {stage.entries.length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {stage.entries.map((entry, i) => (
                      <li
                        key={`${entry.kind}-${entry.deadlineKind ?? ""}-${i}`}
                        className="rounded-xl border border-line bg-surface p-3 break-words"
                      >
                        <Fragment>{entryLabel(entry)}</Fragment>
                        {entry.estimated && (
                          <p className="mt-1 text-sm text-muted">{t.timeline.estimatedHelp}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
