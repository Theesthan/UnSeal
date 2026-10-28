"use client";

import Link from "next/link";
import { useI18n } from "./I18nProvider";
import { FlagList } from "./FlagList";
import { AlertIcon, RetryIcon } from "./icons";
import { BlockedError, isApiError, type ApiErrorCode } from "@/lib/api";
import { format } from "@/lib/i18n-core";
import { REPLY_MAX_MB, REPLY_MAX_PAGES } from "@/lib/reply-limits";
import type { Messages } from "@/messages/types";

export interface ErrorNoticeProps {
  error: unknown;
  /** Re-runs the failed action. Shown only for errors that may succeed on a second try. */
  onRetry?: () => void;
}

function messageFor(code: ApiErrorCode, t: Messages): string {
  switch (code) {
    case "busy":
    case "ask_user":
    case "incomplete":
    case "blocked":
    case "rate_limited":
    case "no_session":
    case "not_found":
    case "invalid":
    case "network":
    case "wrong_status":
    case "invalid_grounds":
    case "invalid_payment_mode":
    case "consent_required":
    case "unreadable_file":
    case "too_many_pages":
    case "length_required":
    case "too_large":
      return format(t.errors[code], { mb: REPLY_MAX_MB, pages: REPLY_MAX_PAGES });
    default:
      return t.errors.generic;
  }
}

/** Every failure gets a worded message and a way forward: never a blank screen. */
export function ErrorNotice({ error, onRetry }: ErrorNoticeProps) {
  const { t, lang } = useI18n();
  const apiError = isApiError(error) ? error : null;
  const message = apiError ? messageFor(apiError.code, t) : t.errors.generic;
  const retryable = apiError ? apiError.retryable : true;
  const tone = apiError?.code === "busy" || apiError?.code === "rate_limited" ? "box-warn" : "box-danger";

  return (
    <div role="alert" className={`${tone} space-y-3`}>
      <p className="flex gap-2 font-semibold break-words">
        <AlertIcon />
        <span>{message}</span>
      </p>
      {error instanceof BlockedError && error.flags.length > 0 && <FlagList flags={error.flags} />}
      <div className="flex flex-col gap-2 sm:flex-row">
        {retryable && onRetry && (
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            <RetryIcon />
            {t.common.retry}
          </button>
        )}
        {apiError?.code === "no_session" && (
          <Link href={`/${lang}`} className="btn btn-secondary">
            {t.errors.noSessionAction}
          </Link>
        )}
        {apiError?.code === "not_found" && (
          <Link href={`/${lang}/cases`} className="btn btn-secondary">
            {t.errors.notFoundAction}
          </Link>
        )}
      </div>
    </div>
  );
}
