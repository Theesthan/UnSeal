import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "@/components/I18nProvider";
import { getMessages } from "@/lib/i18n";
import type { Language } from "@/lib/types";

export function renderWithI18n(ui: ReactElement, lang: Language = "en"): RenderResult {
  return render(
    <I18nProvider lang={lang} messages={getMessages(lang)}>
      {ui}
    </I18nProvider>,
  );
}
