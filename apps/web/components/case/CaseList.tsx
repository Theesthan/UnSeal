"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon, ClockIcon } from "../icons";
import { StatusBadge } from "./StatusBadge";
import { api, isApiError } from "@/lib/api";
import { format, formatDate, formatDateTime, formatDayOf } from "@/lib/i18n-core";
import type { CaseSummary } from "@/lib/types";
import { useAction } from "@/lib/use-action";

/** FR-7 dashboard: every case with its status and next deadline. Cards at every width. */
export function CaseList() {
  const { t, lang } = useI18n();
  const d = t.dashboard;
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const load = useAction(() => api.listCases());
  const runLoad = load.run;

  useEffect(() => {
    runLoad().then((list) => {
      if (list) setCases(list);
    });
  }, [runLoad]);

  const deadlineLabels = t.timeline.deadlines as Record<string, string>;
  const noSession = isApiError(load.error) && load.error.code === "no_session";

  return (
    <div className="page max-w-5xl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="page-title">{d.title}</h1>
        <Link href={`/${lang}/new`} className="btn btn-primary">
          {d.newCase}
          <ArrowIcon />
        </Link>
      </div>

      <div className="mt-8">
        {load.pending && cases === null && (
          <p role="status" className="text-muted">
            {t.common.loading}
          </p>
        )}
        {noSession && <p className="box-info">{d.noSession}</p>}
        {load.error !== null && !noSession && <ErrorNotice error={load.error} onRetry={load.retry} />}
        {cases !== null && cases.length === 0 && <p className="box-info">{d.empty}</p>}
        {cases !== null && cases.length > 0 && (
          <ul className="grid gap-4 md:grid-cols-2">
            {cases.map((c) => {
              const name = c.authority_name ?? d.noAuthority;
              const next = c.next_deadline;
              return (
                <li key={c.id} className="card flex min-w-0 flex-col gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <StatusBadge status={c.status} />
                    <span className="text-sm text-muted">
                      {format(d.started, { date: formatDayOf(c.created_at, lang) })}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold break-words text-ink">{name}</h2>
                  <div className="rounded-xl bg-canvas p-3">
                    <p className="text-sm font-semibold text-muted">{d.nextDeadline}</p>
                    {next && (next.due_at || next.due_on) ? (
                      <p className="mt-1 flex flex-wrap items-center gap-2 font-semibold text-ink">
                        <ClockIcon className="h-5 w-5 text-brand" />
                        <span>{deadlineLabels[next.kind] ?? next.kind}:</span>
                        {next.due_at ? (
                          // The 48-hour track (life or liberty) runs on a timestamp, shown in India time.
                          <time dateTime={next.due_at}>{formatDateTime(next.due_at, lang)}</time>
                        ) : (
                          <time dateTime={next.due_on ?? ""}>{formatDate(next.due_on ?? "", lang)}</time>
                        )}
                        {next.estimated && (
                          <span className="badge border border-[#e8c46a] bg-sun-soft text-sun-ink">
                            {t.common.estimated}
                          </span>
                        )}
                      </p>
                    ) : (
                      <p className="mt-1 text-ink">{d.noDeadline}</p>
                    )}
                  </div>
                  <Link
                    href={`/${lang}/cases/${c.id}`}
                    className="btn btn-secondary mt-auto"
                    aria-label={format(d.openLabel, { name })}
                  >
                    {d.open}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
