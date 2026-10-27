"use client";

import { useId, useState, type FormEvent } from "react";
import { ErrorNotice } from "../ErrorNotice";
import { useI18n } from "../I18nProvider";
import { ArrowIcon } from "../icons";
import { api } from "@/lib/api";
import { format } from "@/lib/i18n-core";
import { JURISDICTIONS, type Authority, type Case, type Jurisdiction } from "@/lib/types";
import { useAction } from "@/lib/use-action";

interface StepAuthorityProps {
  caseData: Case;
  candidates: Authority[];
  jurisdictionHint: string | null;
  onSaved: (updated: Case) => void;
  onBack: () => void;
}

const isJurisdiction = (v: string | null | undefined): v is Jurisdiction =>
  (JURISDICTIONS as readonly string[]).includes(v ?? "");

/** The authority's name in the language of the application, when the list has it. */
function localName(a: Authority, language: string): string {
  if (language === "ta" && a.name_ta) return a.name_ta;
  if (language === "hi" && a.name_hi) return a.name_hi;
  return a.name;
}

type FieldErrors = Partial<Record<"jurisdiction" | "name" | "address", string>>;

/** FR-4: the user picks or types the authority and confirms the PIO address before any PDF. */
export function StepAuthority({
  caseData,
  candidates,
  jurisdictionHint,
  onSaved,
  onBack,
}: StepAuthorityProps) {
  const { t } = useI18n();
  const a = t.flow.authority;
  const ids = useId();
  const [results, setResults] = useState<Authority[]>(candidates);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const initialJurisdiction = isJurisdiction(caseData.jurisdiction)
    ? caseData.jurisdiction
    : isJurisdiction(jurisdictionHint)
      ? jurisdictionHint
      : null;
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction | null>(initialJurisdiction);
  const [name, setName] = useState(caseData.authority_name ?? "");
  const [address, setAddress] = useState(caseData.pio_address ?? "");
  const [viaApio, setViaApio] = useState(caseData.via_apio);
  const [thirdParty, setThirdParty] = useState(caseData.third_party);
  const [lifeLiberty, setLifeLiberty] = useState(caseData.life_liberty);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [searched, setSearched] = useState(false);

  const search = useAction((q: string, j: Jurisdiction | undefined) => api.searchAuthorities(q, j));
  const save = useAction((body: Parameters<typeof api.setAuthority>[1]) =>
    api.setAuthority(caseData.id, body),
  );

  function choose(authority: Authority) {
    setSelectedId(authority.id);
    setName(localName(authority, caseData.language));
    setAddress(authority.pio_address ?? "");
    if (isJurisdiction(authority.jurisdiction)) setJurisdiction(authority.jurisdiction);
  }

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    const found = await search.run(query.trim(), jurisdiction ?? undefined);
    if (found) {
      setResults(found);
      setSearched(true);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: FieldErrors = {};
    if (!jurisdiction) next.jurisdiction = a.jurisdictionRequired;
    if (!name.trim()) next.name = a.nameRequired;
    if (!address.trim()) next.address = a.addressRequired;
    setErrors(next);
    if (Object.keys(next).length > 0 || !jurisdiction) return;
    const updated = await save.run({
      jurisdiction,
      authority_name: name.trim(),
      pio_address: address.trim(),
      via_apio: viaApio,
      third_party: thirdParty,
      life_liberty: lifeLiberty,
    });
    if (updated) onSaved(updated);
  }

  const errorProps = (field: keyof FieldErrors) =>
    errors[field]
      ? { "aria-invalid": "true" as const, "aria-describedby": `${ids}-${field}-error` }
      : {};
  const errorText = (field: keyof FieldErrors) =>
    errors[field] ? (
      <p id={`${ids}-${field}-error`} role="alert" className="field-error">
        {errors[field]}
      </p>
    ) : null;
  const contentLang = caseData.language;

  return (
    <div className="space-y-6">
      <p className="text-muted">{a.hint}</p>

      <form onSubmit={submitSearch} className="card space-y-3" role="search">
        <label htmlFor={`${ids}-q`} className="field-label">
          {a.searchLabel}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${ids}-q`}
            type="search"
            className="field-input mt-0 sm:flex-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary" disabled={search.pending}>
            {search.pending ? a.searching : a.searchButton}
          </button>
        </div>
        {search.error !== null && <ErrorNotice error={search.error} onRetry={search.retry} />}
      </form>

      {results.length > 0 ? (
        <fieldset className="space-y-3">
          <legend className="field-label">{a.suggested}</legend>
          {results.map((authority) => (
            <label
              key={authority.id}
              className="card flex cursor-pointer gap-3 has-[:checked]:border-brand has-[:checked]:ring-2 has-[:checked]:ring-brand"
            >
              <input
                type="radio"
                name="authority-choice"
                className="mt-1.5 h-5 w-5 shrink-0 accent-brand"
                checked={selectedId === authority.id}
                onChange={() => choose(authority)}
              />
              <span className="min-w-0 space-y-1">
                <span lang={contentLang} className="block text-lg font-bold break-words text-ink">
                  {localName(authority, caseData.language)}
                </span>
                {authority.pio_designation && (
                  <span className="block text-muted">
                    {format(a.officer, { designation: authority.pio_designation })}
                  </span>
                )}
                {authority.pio_address && (
                  <span className="block break-words whitespace-pre-line">{authority.pio_address}</span>
                )}
                {authority.rti_online && (
                  <span className="badge bg-brand-soft text-brand-strong">{a.online}</span>
                )}
              </span>
            </label>
          ))}
        </fieldset>
      ) : (
        searched && <p role="status" className="box-info">{a.noResults}</p>
      )}

      <form onSubmit={submit} noValidate className="card space-y-5">
        <fieldset>
          <legend className="field-label">{a.jurisdictionLabel}</legend>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            {JURISDICTIONS.map((j) => (
              <label
                key={j}
                className="flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border-2 border-line px-4 has-[:checked]:border-brand has-[:checked]:bg-brand-soft"
              >
                <input
                  type="radio"
                  name="jurisdiction"
                  value={j}
                  className="h-5 w-5 accent-brand"
                  checked={jurisdiction === j}
                  onChange={() => setJurisdiction(j)}
                  {...errorProps("jurisdiction")}
                />
                {t.jurisdictions[j]}
              </label>
            ))}
          </div>
          {errorText("jurisdiction")}
        </fieldset>

        <div>
          <label htmlFor={`${ids}-name`} className="field-label">
            {a.nameLabel}
          </label>
          <input
            id={`${ids}-name`}
            lang={contentLang}
            className="field-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            {...errorProps("name")}
          />
          {errorText("name")}
        </div>

        <div>
          <label htmlFor={`${ids}-address`} className="field-label">
            {a.addressLabel}
          </label>
          <p id={`${ids}-address-hint`} className="field-hint">
            {a.addressHint}
          </p>
          <textarea
            id={`${ids}-address`}
            lang={contentLang}
            className="field-input field-sizing-content min-h-28"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            {...errorProps("address")}
            aria-describedby={
              errors.address ? `${ids}-address-hint ${ids}-address-error` : `${ids}-address-hint`
            }
          />
          {errorText("address")}
        </div>

        <div className="space-y-3">
          {[
            { key: "apio", checked: viaApio, set: setViaApio, label: a.viaApio, hint: null },
            { key: "third", checked: thirdParty, set: setThirdParty, label: a.thirdParty, hint: null },
            {
              key: "life",
              checked: lifeLiberty,
              set: setLifeLiberty,
              label: a.lifeLiberty,
              hint: a.lifeLibertyHint,
            },
          ].map((box) => (
            <div key={box.key} className="flex items-start gap-3">
              <input
                id={`${ids}-${box.key}`}
                type="checkbox"
                className="mt-1 h-5 w-5 shrink-0 accent-brand"
                checked={box.checked}
                onChange={(e) => box.set(e.target.checked)}
                aria-describedby={box.hint ? `${ids}-${box.key}-hint` : undefined}
              />
              <div>
                <label htmlFor={`${ids}-${box.key}`} className="cursor-pointer font-medium text-ink">
                  {box.label}
                </label>
                {box.hint && (
                  <p id={`${ids}-${box.key}-hint`} className="field-hint">
                    {box.hint}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>

        {save.error !== null && <ErrorNotice error={save.error} onRetry={save.retry} />}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
          <button type="button" className="btn btn-quiet" onClick={onBack}>
            {t.common.back}
          </button>
          <button type="submit" className="btn btn-primary" disabled={save.pending}>
            {save.pending ? a.saving : a.confirm}
            {!save.pending && <ArrowIcon />}
          </button>
        </div>
      </form>
    </div>
  );
}
