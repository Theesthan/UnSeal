"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { ConfirmAction } from "../ConfirmAction";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon } from "../icons";
import { Timeline } from "../Timeline";
import { AppealPanel } from "./AppealPanel";
import { ReceiptForm } from "./ReceiptForm";
import { ReplyDateForm } from "./ReplyDateForm";
import { ReplyReader } from "./ReplyReader";
import { StatusBadge } from "./StatusBadge";
import { api } from "@/lib/api";
import { appealState } from "@/lib/appeal";
import { todayInIndia } from "@/lib/i18n-core";
import type { Case } from "@/lib/types";
import { useAction } from "@/lib/use-action";

// What each status allows, matching the API (docs/api.md): it rejects anything else with
// 409 wrong_status, which the page words too.
const CAN_SET_RECEIPT = new Set(["reply_due"]);
const CAN_READ_REPLY = new Set(["reply_due", "deemed_refused", "replied"]);
const CAN_RECORD_REPLY = new Set(["reply_due", "deemed_refused"]);

/**
 * One case: status, the vertical timeline, and what can happen next: the actual receipt date,
 * the reply (read from a photo or typed in), the first appeal, close and delete (FR-7 to FR-11).
 */
export function CaseDetail({ id }: { id: string }) {
  const { t, lang } = useI18n();
  const c = t.caseDetail;
  const ids = useId();
  const router = useRouter();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [suggestedGrounds, setSuggestedGrounds] = useState<string[] | null>(null);
  const appealRef = useRef<HTMLDivElement>(null);
  const load = useAction(() => api.getCase(id));
  const close = useAction(() => api.closeCase(id));
  const remove = useAction(async () => {
    await api.deleteCase(id);
    router.push(`/${lang}/cases`);
    return true;
  });
  const runLoad = load.run;

  useEffect(() => {
    runLoad().then((loaded) => {
      if (loaded) setCaseData(loaded);
    });
  }, [runLoad]);

  // After the reply letter is read, take the user to the appeal with its grounds ticked.
  useEffect(() => {
    if (suggestedGrounds === null) return;
    appealRef.current?.querySelector<HTMLElement>("h3")?.focus();
  }, [suggestedGrounds]);

  async function confirmClose() {
    const updated = await close.run();
    if (updated) setCaseData(updated);
    return Boolean(updated);
  }

  if (!caseData) {
    return (
      <div className="page">
        {load.error !== null ? (
          <ErrorNotice error={load.error} onRetry={load.retry} />
        ) : (
          <p role="status" className="text-muted">
            {t.common.loading}
          </p>
        )}
      </div>
    );
  }

  const jurisdictions = t.jurisdictions as Record<string, string>;
  const appeal = appealState(caseData, todayInIndia());
  const open = caseData.status !== "closed" && caseData.status !== "draft";

  return (
    <div className="page">
      <Link href={`/${lang}/cases`} className="btn btn-quiet -ms-5">
        {c.back}
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="page-title">{c.title}</h1>
        <StatusBadge status={caseData.status} />
      </div>
      <dl className="card mt-6 grid gap-3 sm:grid-cols-[auto_1fr] sm:gap-x-6">
        <dt className="font-semibold text-muted">{c.authority}</dt>
        <dd lang={caseData.language} className="min-w-0 break-words text-ink">
          {caseData.authority_name ?? c.noAuthority}
          {caseData.jurisdiction && (
            <span lang={lang} className="block text-sm text-muted">
              {jurisdictions[caseData.jurisdiction] ?? caseData.jurisdiction}
            </span>
          )}
        </dd>
      </dl>

      {caseData.status === "draft" && (
        <Link href={`/${lang}/new?case=${caseData.id}`} className="btn btn-primary mt-6 w-full sm:w-auto">
          {c.continueDraft}
          <ArrowIcon />
        </Link>
      )}

      <section aria-labelledby={`${ids}-timeline`} className="mt-8">
        <h2 id={`${ids}-timeline`} className="mb-4 text-2xl font-bold text-ink">
          {t.timeline.title}
        </h2>
        <Timeline caseData={caseData} />
      </section>

      {open && (
        <section aria-labelledby={`${ids}-actions`} className="mt-10 space-y-6">
          <h2 id={`${ids}-actions`} className="text-2xl font-bold text-ink">
            {c.actionsTitle}
          </h2>
          {CAN_SET_RECEIPT.has(caseData.status) && (
            <ReceiptForm caseData={caseData} onUpdated={setCaseData} />
          )}
          {CAN_READ_REPLY.has(caseData.status) && (
            <ReplyReader caseData={caseData} onCaseUpdated={setCaseData} onGrounds={setSuggestedGrounds} />
          )}
          {CAN_RECORD_REPLY.has(caseData.status) && (
            <ReplyDateForm caseData={caseData} onUpdated={setCaseData} />
          )}
          {appeal.canDraft && (
            <div ref={appealRef}>
              <AppealPanel
                // A fresh panel when the reader suggests grounds, so they arrive ticked.
                key={suggestedGrounds?.join(",") ?? "none"}
                caseData={caseData}
                suggestedGrounds={suggestedGrounds}
                onCaseUpdated={setCaseData}
              />
            </div>
          )}
          {close.error !== null && <ErrorNotice error={close.error} onRetry={close.retry} />}
          <ConfirmAction
            label={c.close}
            confirmText={c.closeConfirm}
            confirmLabel={c.closeYes}
            pendingLabel={c.closing}
            pending={close.pending}
            danger={false}
            onConfirm={confirmClose}
          />
        </section>
      )}

      <section className="mt-10 border-t border-line pt-6">
        {remove.error !== null && <ErrorNotice error={remove.error} onRetry={remove.retry} />}
        <ConfirmAction
          label={c.delete}
          confirmText={c.deleteConfirm}
          confirmLabel={c.deleteYes}
          pendingLabel={c.deleting}
          pending={remove.pending}
          onConfirm={remove.run}
        />
      </section>
    </div>
  );
}
