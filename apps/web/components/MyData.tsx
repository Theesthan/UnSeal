"use client";

import Link from "next/link";
import { useState } from "react";
import { ConfirmAction } from "./ConfirmAction";
import { ErrorNotice } from "./ErrorNotice";
import { useI18n } from "./I18nProvider";
import { CheckIcon } from "./icons";
import { api, isApiError } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { clearSessionFlag } from "@/lib/session-flag";
import { useAction } from "@/lib/use-action";

/** FR-8: export everything, or delete everything, each behind a confirm step. */
export function MyData() {
  const { t, lang } = useI18n();
  const m = t.myData;
  const [exported, setExported] = useState(false);
  const [deleted, setDeleted] = useState(false);

  const exportData = useAction(async () => {
    const file = await api.exportMe();
    saveBlob(file, "unseal-my-data.json");
    return true;
  });
  const deleteData = useAction(async () => {
    await api.deleteMe();
    clearSessionFlag();
    return true;
  });

  async function confirmExport() {
    setExported(false);
    const ok = await exportData.run();
    if (ok) setExported(true);
    return ok;
  }

  async function confirmDelete() {
    const ok = await deleteData.run();
    if (ok) setDeleted(true);
    return ok;
  }

  const noSession = (error: unknown) => isApiError(error) && error.code === "no_session";

  if (deleted) {
    return (
      <div className="page space-y-6">
        <h1 className="page-title">{m.title}</h1>
        <p role="status" className="box-ok flex gap-2 text-lg font-semibold">
          <CheckIcon />
          <span>{m.deleted}</span>
        </p>
        <Link href={`/${lang}`} className="btn btn-primary">
          {t.notFound.home}
        </Link>
      </div>
    );
  }

  return (
    <div className="page space-y-8">
      <div>
        <h1 className="page-title">{m.title}</h1>
        <p className="mt-3 text-lg text-muted">{m.intro}</p>
      </div>

      <section aria-labelledby="export-title" className="card space-y-4">
        <h2 id="export-title" className="text-xl font-bold text-ink">
          {m.exportTitle}
        </h2>
        <p>{m.exportBody}</p>
        {noSession(exportData.error) ? (
          <p className="box-info">{m.noSession}</p>
        ) : (
          exportData.error !== null && <ErrorNotice error={exportData.error} onRetry={exportData.retry} />
        )}
        {exported && (
          <p role="status" className="box-ok flex gap-2 font-semibold">
            <CheckIcon />
            <span>{m.exported}</span>
          </p>
        )}
        <ConfirmAction
          label={m.exportButton}
          confirmText={m.exportConfirm}
          confirmLabel={m.exportYes}
          pendingLabel={m.exporting}
          pending={exportData.pending}
          danger={false}
          onConfirm={confirmExport}
        />
      </section>

      <section aria-labelledby="delete-title" className="card space-y-4 border-[#f0b4ae]">
        <h2 id="delete-title" className="text-xl font-bold text-danger">
          {m.deleteTitle}
        </h2>
        <p>{m.deleteBody}</p>
        {noSession(deleteData.error) ? (
          <p className="box-info">{m.noSession}</p>
        ) : (
          deleteData.error !== null && <ErrorNotice error={deleteData.error} onRetry={deleteData.retry} />
        )}
        <ConfirmAction
          label={m.deleteButton}
          confirmText={m.deleteConfirm}
          confirmLabel={m.deleteYes}
          pendingLabel={m.deleting}
          pending={deleteData.pending}
          onConfirm={confirmDelete}
        />
      </section>
    </div>
  );
}
