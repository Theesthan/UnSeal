"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon, CheckIcon, ShieldIcon } from "../icons";
import { api } from "@/lib/api";
import type { ApplicantBody, Case } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface StepApplicantProps {
  caseData: Case;
  onSaved: () => void;
  onNext: () => void;
  onBack: () => void;
}

const PHONE = /^\+?[0-9][0-9 -]{6,15}$/;
type FieldErrors = Partial<Record<"name" | "address" | "phone", string>>;

/**
 * Applicant name, address and phone go to the API once (stored encrypted) and are never shown
 * back here. After saving, the form is cleared from memory.
 */
export function StepApplicant({ caseData, onSaved, onNext, onBack }: StepApplicantProps) {
  const { t } = useI18n();
  const p = t.flow.applicant;
  const ids = useId();
  const [editing, setEditing] = useState(!caseData.has_applicant);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [bpl, setBpl] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const save = useAction(async (body: ApplicantBody) => {
    await api.setApplicant(caseData.id, body);
    return true;
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: FieldErrors = {};
    if (!name.trim()) next.name = p.nameRequired;
    if (!address.trim()) next.address = p.addressRequired;
    if (phone.trim() && !PHONE.test(phone.trim())) next.phone = p.phoneInvalid;
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    const ok = await save.run({
      name: name.trim(),
      address: address.trim(),
      phone: phone.trim() || null,
      bpl,
    });
    if (ok) {
      setName("");
      setAddress("");
      setPhone("");
      setBpl(false);
      setEditing(false);
      onSaved();
    }
  }

  if (!editing) {
    return (
      <div className="space-y-5">
        <p role="status" className="box-ok flex gap-2 font-semibold">
          <CheckIcon />
          <span>{p.saved}</span>
        </p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" className="btn btn-quiet" onClick={onBack}>
              {t.common.back}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
              {p.replace}
            </button>
          </div>
          <button type="button" className="btn btn-primary" onClick={onNext}>
            {t.common.continue}
            <ArrowIcon />
          </button>
        </div>
      </div>
    );
  }

  const field = (key: keyof FieldErrors) => ({
    id: `${ids}-${key}`,
    "aria-invalid": errors[key] ? ("true" as const) : undefined,
    "aria-describedby": errors[key] ? `${ids}-${key}-error` : undefined,
  });
  const error = (key: keyof FieldErrors) =>
    errors[key] ? (
      <p id={`${ids}-${key}-error`} role="alert" className="field-error">
        {errors[key]}
      </p>
    ) : null;

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <p className="box-info flex gap-2">
        <ShieldIcon />
        <span>{p.hint}</span>
      </p>
      <div>
        <label htmlFor={`${ids}-name`} className="field-label">
          {p.name}
        </label>
        <input
          {...field("name")}
          className="field-input"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {error("name")}
      </div>
      <div>
        <label htmlFor={`${ids}-address`} className="field-label">
          {p.address}
        </label>
        <p className="field-hint">{p.addressHint}</p>
        <textarea
          {...field("address")}
          className="field-input field-sizing-content min-h-28"
          autoComplete="street-address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />
        {error("address")}
      </div>
      <div>
        <label htmlFor={`${ids}-phone`} className="field-label">
          {p.phone} <span className="font-normal text-muted">({t.common.optional})</span>
        </label>
        <input
          {...field("phone")}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          className="field-input"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        {error("phone")}
      </div>
      <div className="flex items-start gap-3">
        <input
          id={`${ids}-bpl`}
          type="checkbox"
          className="mt-1 h-5 w-5 shrink-0 accent-brand"
          checked={bpl}
          onChange={(e) => setBpl(e.target.checked)}
          aria-describedby={`${ids}-bpl-hint`}
        />
        <div>
          <label htmlFor={`${ids}-bpl`} className="cursor-pointer font-medium text-ink">
            {p.bpl}
          </label>
          <p id={`${ids}-bpl-hint`} className="field-hint">
            {p.bplHint}
          </p>
        </div>
      </div>
      {save.error !== null && <ErrorNotice error={save.error} onRetry={save.retry} />}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button
          type="button"
          className="btn btn-quiet"
          onClick={caseData.has_applicant ? () => setEditing(false) : onBack}
        >
          {caseData.has_applicant ? t.common.cancel : t.common.back}
        </button>
        <button type="submit" className="btn btn-primary" disabled={save.pending}>
          {save.pending ? p.saving : p.save}
        </button>
      </div>
    </form>
  );
}
