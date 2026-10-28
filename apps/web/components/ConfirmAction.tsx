"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useI18n } from "./I18nProvider";

interface ConfirmActionProps {
  label: string;
  confirmText: string;
  confirmLabel: string;
  pendingLabel: string;
  pending: boolean;
  danger?: boolean;
  /** Resolve to true when the action succeeded, to fold the confirm step away again. */
  onConfirm: () => Promise<boolean | undefined | void> | void;
}

/**
 * A two-step action for anything that deletes or cannot be undone. The confirm step appears in
 * place (no modal to trap focus in), takes focus, and Cancel puts focus back on the first button.
 */
export function ConfirmAction({
  label,
  confirmText,
  confirmLabel,
  pendingLabel,
  pending,
  danger = true,
  onConfirm,
}: ConfirmActionProps) {
  const { t } = useI18n();
  const ids = useId();
  const [asking, setAsking] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const wasAsking = useRef(false);

  useEffect(() => {
    if (asking) panelRef.current?.focus();
    else if (wasAsking.current) openerRef.current?.focus();
    wasAsking.current = asking;
  }, [asking]);

  if (!asking) {
    return (
      <button
        ref={openerRef}
        type="button"
        className={`btn ${danger ? "btn-secondary border-danger text-danger hover:bg-danger-soft" : "btn-secondary"} w-full sm:w-auto`}
        onClick={() => setAsking(true)}
      >
        {label}
      </button>
    );
  }

  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="group"
      aria-labelledby={`${ids}-text`}
      className={`${danger ? "box-danger" : "box-info"} space-y-3 focus:outline-none`}
    >
      <p id={`${ids}-text`} className="font-semibold">
        {confirmText}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          className={`btn ${danger ? "btn-danger" : "btn-primary"}`}
          disabled={pending}
          onClick={async () => {
            if (await onConfirm()) setAsking(false);
          }}
        >
          {pending ? pendingLabel : confirmLabel}
        </button>
        <button
          type="button"
          className="btn btn-quiet"
          disabled={pending}
          onClick={() => setAsking(false)}
        >
          {t.common.cancel}
        </button>
      </div>
    </div>
  );
}
