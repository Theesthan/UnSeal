"use client";

import { useI18n } from "../I18nProvider";

const TONE: Record<string, string> = {
  draft: "bg-canvas text-ink border border-line",
  filed: "bg-brand-soft text-brand-strong",
  reply_due: "bg-sun text-ink",
  replied: "bg-ok-soft text-ok",
  deemed_refused: "bg-danger-soft text-danger",
  appealed: "bg-brand text-white",
  closed: "bg-line text-ink",
};

/** Status in words (never colour alone); an unknown status shows its raw code. */
export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const labels = t.timeline.statuses as Record<string, string>;
  return (
    <span className={`badge ${TONE[status] ?? "bg-canvas text-ink border border-line"}`}>
      {labels[status] ?? status}
    </span>
  );
}
