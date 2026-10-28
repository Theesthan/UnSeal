"use client";

import { useI18n } from "./I18nProvider";

export function PageLoading() {
  const { t } = useI18n();
  return (
    <div className="page">
      <p role="status" className="text-muted">
        {t.common.loading}
      </p>
    </div>
  );
}
