"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Messages } from "@/messages/types";
import type { Language } from "@/lib/types";

interface I18nValue {
  lang: Language;
  t: Messages;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  lang,
  messages,
  children,
}: {
  lang: Language;
  messages: Messages;
  children: ReactNode;
}) {
  return <I18nContext.Provider value={{ lang, t: messages }}>{children}</I18nContext.Provider>;
}

/** Like useI18n, but returns null outside a provider (for the not-found page). */
export function useOptionalI18n(): I18nValue | null {
  return useContext(I18nContext);
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <I18nProvider>");
  return value;
}
